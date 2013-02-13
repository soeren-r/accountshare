# -*- coding: utf-8 -*-
"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.
    
    @author: Soeren Rinne
    @interface-version: 0.5
"""

"""
    TODO:
    * if lock set by different IP is older than x days, remove it and set own lock
	* what about failed and manually started files of a package? "downloadPreparing"
	  could be the wrong hook in this case.
"""

import time
import urllib2

from module.plugins.Hook import Hook

class AccountShare(Hook):
    __name__ = "AccountShare"
    __version__ = "0.5"
    __description__ = """For account sharing between map and sor"""
    __config__ = [  ("activated" , "bool" , "Activated"  , "True" ),
                    ("scriptUrl", "str", "Url to script", "http://www.soerenrinne.de/rs/status.php?pyload=true"),
                    ("intervalLocked", "int", "Interval in seconds when account is locked (also default on start)", 30),
                    ("intervalUnlocked", "int", "Interval in seconds when account is not locked", 1800)]
    __threaded__ = []
    __author_name__ = ("Soeren Rinne")
    __author_mail__ = ("srinne+accountshare@gmail.com")
    
    
    ########## override functions ##########
    
    def setup(self):
        #callback to scheduler job for getting IP; will be removed by hookmanager when hook unloaded
        self.cb = None
        #set interval for "periodical"
        self.interval = self.getConfig("intervalLocked")
        #get IP on start and in 6h interval (as scheduled job)
        self.getExternalIp()
        #add event listener for "allDownloadsProcessed" #"allDownloadsFinished" does not seem to work always
        self.manager.addEvent("allDownloadsProcessed", self.removeLock)
        
    #will be automatically called on start, not only after first "self.interval" seconds
    def periodical(self):
        #check status online
        self.logDebug("Checking status online.")
        self.checkLockStatus()
        self.logDebug("Processing status.")
        self.processLockStatus()
    
    def downloadPreparing(self, fid):
        #check status online before starting
        self.logDebug("Checking status online before starting download.")
        self.checkLockStatus()
        self.logDebug("Processing status before starting download.")
        self.processLockStatus(periodical=False)
        
    ## tests ##

    #works
    #def downloadPreparing(self, fid):
    #    self.logInfo("A download is getting prepared")
    #    time.sleep(2)
    #    self.logInfo("downloadPreparing: go on")  
    #works
    #def downloadFinished(self, pyfile):
    #    self.logInfo("A download is finished")
    #    time.sleep(2)
    #    self.logInfo("downloadFinished: go on")
    #works
    #def packageFinished(self, pypack):
    #    self.logInfo("A package is finished")
    #    time.sleep(2)
    #    self.logInfo("packageFinished: go on")
        
    ########## own functions ##########
        
    def getExternalIp(self):
        #get source of website
        myIpWebsiteSource = urllib2.urlopen('http://www.see-my-ip.com/index_en.php').read()
        #find location in source
        ipLocation = myIpWebsiteSource.find("Your IP address is ")
        #fetch IP with maximal possible length and split trailing whitespaces
        myIpArray = myIpWebsiteSource[ipLocation+19:ipLocation+34].split()
        #IP should be now in the first element, strip eventually leading whitespaces
        self.ip = myIpArray[0].strip()
        self.logInfo("Periodically checked IP: " + self.ip + ". Will check again in 6h.")
        #remove current job for getting IP (if any)
        self.core.scheduler.removeJob(self.cb)
        #add new jobf ro getting IP. next check is in 6h
        next_time = 21600
        self.cb = self.core.scheduler.addJob(next_time, self.getExternalIp, threaded=True)
    
    def checkLockStatus(self):
        #get source of website
        myRSWebsiteSource = urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?pyload=true').read()
        #split source by lines
        myRSWebsiteSourceArray = myRSWebsiteSource.splitlines()
        # status info should be always in 6th row, afterwards split by comma to separate info
        myRSWebsiteInfoArray = myRSWebsiteSourceArray[5].split(',')
        #lockStatus: ("locked OR unlocked","ip OR empty","time in 'Ymd' OR empty")
        self.lockStatus = myRSWebsiteInfoArray
    
    def processLockStatus(self, periodical=True):
        if self.lockStatus[0] == "locked":
            if self.ip == self.lockStatus[1]:
                #unpause pyload
                self.logInfo("Account locked. Starting download server anyhow due to identical IP (" + self.ip + "). Will check again in " + str(self.getConfig("intervalUnlocked")) + " seconds.")
                self.core.api.unpauseServer()
                #adjust waiting time
                self.interval = self.getConfig("intervalUnlocked")
            else:
                #pause pyload
                self.logInfo("Account locked by " + self.lockStatus[1] + ", but our IP is " + self.ip + ". Stopping download server. Will check again in " + str(self.getConfig("intervalLocked")) + " seconds.")
                self.core.api.pauseServer()
                #adjust waiting time
                self.interval = self.getConfig("intervalLocked")
        elif self.lockStatus[0] == "unlocked":
            #unpause pyload
            self.logInfo("Account unlocked. Starting download server. Will check again in " + str(self.getConfig("intervalUnlocked")) + " seconds.")
            self.core.api.unpauseServer()
            #adjust waiting time
            self.interval = self.getConfig("intervalUnlocked")
            if not periodical:
                #called while starting actual download, so set lock online
                self.setLock()
                
        else:
            #something abnormal happened
            self.logError("Something is wrong with the status. I will set interval to 60 minutes.")
            self.interval = 3600
        
    def removeLock(self):
        #remove lock online
        urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?active=false')
        self.logDebug("Removed lock online.")
        
    def setLock(self):
        #set lock online
        urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?active=true')
        self.logDebug("Set lock online.")

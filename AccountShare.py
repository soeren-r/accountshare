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
    @interface-version: 0.2
"""

"""
    TODO:
    * if lock set by different IP is older than x days, remove it and set own lock
"""

import time
import urllib2

from module.plugins.Hook import Hook

class AccountShare(Hook):
    __name__ = "AccountShare"
    __version__ = "0.6"
    __description__ = """For account sharing between map and sor"""
    __config__ = [  ("activated" , "bool" , "Activated"  , "True" ),
                    ("scriptUrl", "str", "Url to account script", "http://www.soerenrinne.de/rs/status.php?pyload=true"),
                    ("ipUrl", "str", "Url to IP script", "http://www.soerenrinne.de/rs/ip.php"),
                    ("intervalLocked", "int", "Interval in seconds when account is locked", 60),
                    ("intervalIp", "int", "Interval in seconds to check IP", 21600)]
    __threaded__ = []
    __author_name__ = ("Soeren Rinne")
    __author_mail__ = ("srinne+accountshare@gmail.com")
    
    
    ########## override functions ##########
    
    def setup(self):
        #callback to scheduler job for getting IP; will be removed by hookmanager when hook unloaded
        self.cbIp = None
        #callback for scheduler job if account is locked
        self.cbAccount = None
        #get IP on start and in set interval (as scheduled job; default is 6h)
        self.getExternalIp()
        #add event listener for "allDownloadsProcessed" #"allDownloadsFinished" does not seem to work always
        self.manager.addEvent("allDownloadsProcessed", self.removeLock)
    
    def downloadPreparing(self, fid):
        #check status online before starting
        self.logDebug("Getting status online before starting download.")
        self.getLockStatus()
        self.logDebug("Processing status before starting download.")
        self.processLockStatus()
    
    def downloadStarts(self, fid):
        #check status online before starting
        self.logDebug("Getting status online before starting download.")
        self.getLockStatus()
        self.logDebug("Processing status before starting download.")
        self.processLockStatus()
        
    ########## own functions ##########
        
    def getExternalIpProvider(self):
        #get source of website
        myIpWebsiteSource = urllib2.urlopen('http://www.see-my-ip.com/index_en.php').read()
        #find location in source
        ipLocation = myIpWebsiteSource.find("Your IP address is ")
        #fetch IP with maximal possible length and split trailing whitespaces
        myIpArray = myIpWebsiteSource[ipLocation+19:ipLocation+34].split()
        #IP should be now in the first element, strip eventually leading whitespaces
        self.ip = myIpArray[0].strip()
        self.logInfo("Periodically checked IP: " + self.ip + ". Will check again in " + str(self.getConfig("intervalIp")) + " seconds.")
        #remove current job for getting IP (if any)
        self.core.scheduler.removeJob(self.cbIp)
        #add new job for getting IP. next check is in 6h
        next_time = self.getConfig("intervalIp")
        self.cbIp = self.core.scheduler.addJob(next_time, self.getExternalIp, threaded=True)
    
    def getExternalIp(self):
        #get source of website
        myIp = urllib2.urlopen(self.getConfig("ipUrl")).read()
        self.ip = myIp.strip()
        self.logInfo("Periodically checked IP: " + self.ip + ". Will check again in " + str(self.getConfig("intervalIp")) + " seconds.")
        #remove current job for getting IP (if any)
        self.core.scheduler.removeJob(self.cbIp)
        #add new job for getting IP. next check is in 6h
        next_time = self.getConfig("intervalIp")
        self.cbIp = self.core.scheduler.addJob(next_time, self.getExternalIp, threaded=True)
    
    def getLockStatus(self):
        #get source of website
        myRSWebsiteSource = urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?pyload=true').read()
        #split source by lines
        myRSWebsiteSourceArray = myRSWebsiteSource.splitlines()
        # status info should be always in 6th row, afterwards split by comma to separate info
        myRSWebsiteInfoArray = myRSWebsiteSourceArray[5].split(',')
        #lockStatus: "locked" OR "unlocked"
        self.lockStatus = myRSWebsiteInfoArray[0]
        #lockIp: ip OR empty
        self.lockIp = myRSWebsiteInfoArray[1]
        #lockTime: time in 'Ymd' OR empty
        self.lockTime = myRSWebsiteInfoArray[2]
    
    def processLockStatus(self):
        if self.lockStatus == "locked":
            if self.ip == self.lockIp:
                #unpause pyload
                self.logInfo("Account locked. Unpausing download server anyhow due to identical IP (" + self.ip + ").")
                self.core.api.unpauseServer()
                self.core.scheduler.removeJob(self.cbAccount)
            else:
                #pause pyload
                self.logInfo("Account locked by " + self.lockIp + ", but our IP is " + self.ip + ". Paused download server. Will check again in " + str(self.getConfig("intervalLocked")) + " seconds.")
                self.core.api.pauseServer()
                #add new job for checking account status. next check is in "intervalLocked"
                next_time = self.getConfig("intervalLocked")
                self.core.scheduler.removeJob(self.cbAccount)
                self.cbAccount = self.core.scheduler.addJob(next_time, self.processLockStatus, threaded=False)
        elif self.lockStatus == "unlocked":
            #called while starting actual download, so set lock online
            self.setLock()
            #unpause pyload
            self.logInfo("Account unlocked. Unpausing server.")
            self.core.api.unpauseServer()
            #remove old job
            self.core.scheduler.removeJob(self.cbAccount)
                
        else:
            #something abnormal happened
            self.logError("Something is wrong with the status.")
        
    def removeLock(self):
        self.logDebug("All downloads processed. Trying now to remove lock.")
        for i in range(5):
            #remove lock online
            urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?active=false')
            #now check if really removed
            self.getLockStatus()
            if self.lockStatus == "unlocked":
                self.logDebug("Removed lock online after " + str(i+1) + " tries.")
                break
            else:
                self.logDebug("Did not remove lock online. Will try again " + str(5-i-1) + " times.")
        
    def setLock(self):
        for i in range(5):
            #set lock online
            urllib2.urlopen('http://www.soerenrinne.de/rs/status.php?active=true')
            #now check if really set
            self.getLockStatus()
            if self.lockStatus == "locked":
                self.logDebug("Set lock online after " + str(i+1) + " tries.")
                break
            else:
                self.logDebug("Did not set lock online. Will try again " + str(5-i-1) + " times.")

import threading ;
import time ;
from lpiot.ipcpacket import IPMeta ;
from lpiot.sensormodel import SensorMeta ;
from lpiot.sensordb import SensorDB, SensorLogDB ;
from libps.psDebug import DBG, ERR ;
# import ctypes ;

class DBManager(threading.Thread) :
    DB_UPDATE_INTERVAL_SECOND = 5 ;
    DB_IDLE_SECOND = 1 ;
    def __init__(self, ippHandle) :
        threading.Thread.__init__(self) ;
        self.m_ippHandle = ippHandle ;
        self.m_sdb = SensorDB() ;
        self.m_ldb = SensorLogDB() ;
        self.m_ippHandle.register(IPMeta.SUBTYPE_SYSTEM, self.receivedSystemEvent) ;
        self.m_ippHandle.register(IPMeta.SUBTYPE_SENSOR, self.receivedSensorEvent) ;
        self.m_ippHandle.register(IPMeta.SUBTYPE_DB, self.receivedDatabaseQuery) ;
        self.m_sensorPool = [] ;
        self.m_queryPool = [] ;
        self.m_lockDB = threading.Lock() ;
        self.m_eventQuery = threading.Event() ;
        self.m_lastUpdateTime = 0 ;
        self.fgRun = True ;
        self.start() ;
    def __flushSensorPool(self) :
        with self.m_lockDB :
            if len(self.m_sensorPool) > 0 :
                self.m_sdb.queryUpsert(self.m_sensorPool) ;
                self.m_sensorPool = [] ;
        self.m_lastUpdateTime = time.time() ;
    def __flushQueryPool(self) :
        if len(self.m_queryPool) > 0 :
            self.__flushSensorPool() ;
            with self.m_lockDB :
                for ipId, payload in self.m_queryPool :
                    argv = payload.split('|') ;
                    if argv[0] == 'GetNode' :
                        self.m_ippHandle.sendQueryReply(True, ipId, IPMeta.SUBTYPE_DB, self.m_sdb.queryGetTable('sensor_node')) ;
                    elif argv[0] == 'GetCluster' :
                        self.m_ippHandle.sendQueryReply(True, ipId, IPMeta.SUBTYPE_DB, self.m_sdb.queryGetTable('sensor_cluster')) ;
                    elif argv[0] == 'GetAttribute' :
                        self.m_ippHandle.sendQueryReply(True, ipId, IPMeta.SUBTYPE_DB, self.m_sdb.queryGetTable('sensor_attribute')) ;
                    else :
                        self.m_ippHandle.sendQueryReply(False, ipId, IPMeta.SUBTYPE_DB, 'Unknown Query(%s)' % payload) ;
                self.m_queryPool = [] ;
                self.m_eventQuery.clear() ;

    def receivedSystemEvent(self, ipId, ipSType, ipPayload) :
        DBG('[EVENT] %s %s %s' % (ipId, ipSType, ipPayload)) ;
        if ipId == '00000000' and ipSType == IPMeta.SUBTYPE_SYSTEM :
            if ipPayload == 'quit' :
                self.stop() ;
    def receivedSensorEvent(self, ipId, ipSType, ipPayload) :
        DBG('[EVENT] %s %s %s' % (ipId, ipSType, ipPayload)) ;
        with self.m_lockDB :
            self.m_sensorPool.append([ipSType, ipPayload]) ;
    def receivedDatabaseQuery(self, ipId, ipSType, ipPayload) :
        DBG('[QUERY] %s %s %s' % (ipId, ipSType, ipPayload)) ;
        with self.m_lockDB :
            self.m_queryPool.append([ipId, ipPayload]) ;
            self.m_eventQuery.set() ;
    def run(self) :
        # DBG('DBManager = %d' % ctypes.CDLL('libc.so.6').syscall(224)) ;
        DBG('Start of DBManager') ;
        while self.fgRun :
            self.m_eventQuery.wait(DBManager.DB_IDLE_SECOND) ;
            self.__flushQueryPool() ;
            if (time.time() - self.m_lastUpdateTime) > DBManager.DB_UPDATE_INTERVAL_SECOND :
                self.__flushSensorPool() ;
        self.__flushSensorPool() ;
        DBG('End of DBManager') ;
    def stop(self) :
        self.fgRun = False ;
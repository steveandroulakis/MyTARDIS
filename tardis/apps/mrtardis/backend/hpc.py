# To change this template, choose Tools | Templates
# and open the template in the editor.

__author__="grischa"
__date__ ="$17/09/2010 3:02:10 PM$"

if __name__ == "__main__":
    print "Hello World"

# IMPORTS
import paramiko
import StringIO
import stat

class hpc:
    types = ("sge","pbs")
    type = None
    hostname = None
    username = None
    privateKey = None
    authtype = "key"
    client = None
    sftpclient = None

    def __init__(self, hostname, username, type = "sge", authtype = "key", key = None, keytype = None):
        self.type = type
        self.hostname = hostname
        self.username = username
        self.authtype = authtype
        if authtype == "key":
            self.setKey(key, keytype)
        self.client = paramiko.SSHClient()
        policy = paramiko.AutoAddPolicy()
        self.client.set_missing_host_key_policy(policy)
        self.client.connect(hostname = self.hostname,username = self.username, pkey = self.privateKey)


    def setKey(self, privateKeyString, keytype):
        privateKeyFileObj = StringIO.StringIO(privateKeyString)
        if keytype == "rsa":
            self.privateKey = paramiko.RSAKey.from_private_key(privateKeyFileObj)
        elif keytype == "dsa":
            self.privateKey = paramiko.DSAKey.from_private_key(privateKeyFileObj)
    
    def initSFTP(self):
        if self.sftpclient == None:
            self.sftpclient = paramiko.SFTPClient.from_transport(self.client.get_transport())

    def upload(self, remoterelativepath, filelist, localpath = ""):
        """upload files to hpc using path parameters"""
        self.initSFTP()
        remotepath = "/nfs/monash/home/" + self.username + "/"+ remoterelativepath
        self.sftpclient.mkdir(remotepath)
        for file in filelist:
            localfilepath = localpath + "/" + file
            remotefilepath = remotepath + "/" + file
            #print remotefilepath
            self.sftpclient.put(localfilepath, remotefilepath, callback=None)

    def download(self, remotepath, localpath, filelist = None, excludefiles = None):
        self.initSFTP()
        if filelist == None:
            filelist = self.sftpclient.listdir(remotepath)
        filteredlist = []
        if excludefiles != None:
            for file in filelist:
                if file not in excludefiles:
                    filteredlist.append(file)
        else:
            filteredlist = filelist
        for file in filteredlist:
            localfilepath = localpath + "/" + file
            remotefilepath = remotepath + "/" + file
            self.sftpclient.get(remotefilepath, localfilepath)

    def testConnection(self):
        (testhost, dud) = self.getOutputError("hostname")
        #print testhost
        #print self.hostname
        if testhost.strip() == self.hostname.strip():
            return True
        else:
            return False

    def getOutputError(self, command):
        stdin, stdout,  stderr = self.client.exec_command(command)
        retout = stdout.read()
        reterr = stderr.read()
        stdin.close()
        stdout.close()
        stderr.close()
        return (retout, reterr)

    def rmtree(self, path):
        self.initSFTP()
        pathstat = self.sftpclient.lstat(path)
        #print path
        if stat.S_ISDIR(pathstat.st_mode):
            list = self.sftpclient.listdir(path)
            if len(list) > 0:
                for file in list:
                    filename = path + "/" + file
                    filestat = self.sftpclient.lstat(filename)
                    if stat.S_ISDIR(filestat.st_mode):
                        self.rmtree(filename)
                    else:
                        self.sftpclient.remove(filename)
            self.sftpclient.rmdir(path)
        else:
            self.sftpclient.remove(path)

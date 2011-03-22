# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Monash e-Research Centre
#   (Monash University, Australia)
# Copyright (c) 2010, VeRSI Consortium
#   (Victorian eResearch Strategic Initiative, Australia)
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    *  Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    *  Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#    *  Neither the name of the VeRSI, the VeRSI Consortium members, nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE7
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
"""
admin.py

.. moduleauthor::  Grischa Meyer <grischa.meyer@monash.edu>

"""

import paramiko
import StringIO
import stat
import os

from tardis.tardis_portal.logger import logger

import tardis.apps.mrtardis.secrets as secrets


class HPC:
    """
    Simplified interface to HPC resources using the paramiko ssh library.
    Currently implemented:
    Monash Sun Grid ("msg")
    """
    types = ("sge", "pbs")
    queuetype = None
    hostname = None
    username = None
    privateKey = None
    authtype = "key"
    client = None
    sftpclient = None

    def __init__(self, location, username):
        """
        Initialise object using a predefined cluster location string and the
        username to be used for ssh.
        :param location: predefined string for HPC resource to be used.
            currently defined: "msg"
        :type location: string
        :param username: username used for ssh-ing into HPC resource
        :type username: string
        """
        self.username = username
        if location == "msg":
            self.queuetype = "sge"
            self.hostname = secrets.hostname
            self.authtype = "key"
            key = secrets.privatekey
            keytype = "rsa"
        if self.authtype == "key":
            self.setKey(key, keytype)
        self.client = paramiko.SSHClient()
        policy = paramiko.AutoAddPolicy()
        self.client.set_missing_host_key_policy(policy)
        self.client.connect(hostname=self.hostname, username=self.username,
                            pkey=self.privateKey)

    def __del__(self):
        """
        closes client when object is destroyed/dereferenced
        """
        if self.client != None:
            try:
                self.client.close()
            except:
                pass

    def setKey(self, privateKeyString, keytype):
        """
        sets the private key to be used for ssh using a string and keytype
        :param privateKeyString: string with ssh private key
        :type privateKeyString: string
        :param keytype: type of key entered, one of "rsa", "dss"
        :type keytype: string
        """
        privateKeyFileObj = StringIO.StringIO(privateKeyString)
        if keytype == "rsa":
            self.privateKey = paramiko.RSAKey.from_private_key(
                privateKeyFileObj)
        elif keytype == "dss":
            self.privateKey = paramiko.DSSKey.from_private_key(
                privateKeyFileObj)

    def initSFTP(self):
        """
        initialises the use of SFTP and stores it in instance
        """
        if self.sftpclient == None:
            self.sftpclient = paramiko.SFTPClient.from_transport(
                self.client.get_transport())

    def upload(self, localfilepath, remotefile):
        """
        BROKEN
        uploads a file to remote location
        :param localfilepath: full path to local file
        :param remotedir:
        """
        self.initSFTP()
        self.getOutputError("mkdir -p ~/%s" % os.path.dirname(remotefile))
        try:
            self.sftpclient.put(localfilepath, self.getHomeDir() + "/"
                                + remotefile)
        except IOError:
            print "IOError... shit"
            print localfilepath
            print self.getHomeDir() + "/" + remotefile

    def upload_filelist(self, remoterelativepath, filelist, localpath=""):
        """
        upload files to hpc using path parameters
        """
        self.initSFTP()
        remotepath = "/nfs/monash/home/" + self.username +\
            "/" + remoterelativepath
        self.sftpclient.mkdir(remotepath)
        for filename in filelist:
            localfilepath = localpath + "/" + filename
            remotefilepath = remotepath + "/" + filename
            #print remotefilepath
            self.sftpclient.put(localfilepath, remotefilepath, callback=None)

    def download(self, remotepath, localpath,
                 filelist=None, excludefiles=None):
        self.initSFTP()
        if filelist == None:
            filelist = self.sftpclient.listdir(remotepath)
        filteredlist = []
        if excludefiles != None:
            for filename in filelist:
                if filename not in excludefiles:
                    filteredlist.append(filename)
        else:
            filteredlist = filelist
        for filename in filteredlist:
            localfilepath = localpath + "/" + filename
            remotefilepath = remotepath + "/" + filename
            self.sftpclient.get(remotefilepath, localfilepath)
        return filteredlist

    def testConnection(self):
        testhost = self.getOutputError("hostname")[0]
        #print testhost
        #print self.hostname
        logger.debug("testing connection in hpc.py")
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

    def runCommands(self, commandlist):
        return [self.getOutputError(command) for command in commandlist]

    def getHomeDir(self):
        out, err = self.getOutputError("echo $HOME")
        return out.strip()

    def rmtree(self, path):
        self.initSFTP()
        pathstat = self.sftpclient.lstat(path)
        #print path
        if stat.S_ISDIR(pathstat.st_mode):
            filelist = self.sftpclient.listdir(path)
            if len(filelist) > 0:
                for filebasename in filelist:
                    filename = path + "/" + filebasename
                    filestat = self.sftpclient.lstat(filename)
                    if stat.S_ISDIR(filestat.st_mode):
                        self.rmtree(filename)
                    else:
                        self.sftpclient.remove(filename)
            self.sftpclient.rmdir(path)
        else:
            self.sftpclient.remove(path)

    @staticmethod
    def getPublicKey():
        return secrets.publickey

#!/usr/bin/env python2
# -*- coding: utf8 -*-
# vim:fileencoding=utf8

from __future__ import print_function;
from Tkinter import *
import SoapySDR
from SoapySDR import *
import sys;

# things we want to set for each channel:
# - Gain
# - - name 
# - - bool hasGainMode() // AGC
# - - setGainMode(bool() // AGC
# - - bool getGainMode() // AGC
# - - setGain(double) // overall amp.
# - - double getGain() // overall
# - - Range getGainRange() // overall
# - - setGain(gainname, double)
# - - double getGain(ganname)
# - - Range getGainRange(gainname)
# - Bandwidth
# - - setBandwidth(double)
# - - double getBandwidth()
# - - std::vector<double> listBandwidths() DEPRECATED
# - - RangeList getBandwidthRange()
# - Settings API
# - -device settings:
# - - ArgInfoList getSettingInfo() // returns a list of argument info structures. NO direction and channel argument!
# - - writeSetting(string key, value)
# - - template <typename Type> writeSetting(string key, Type &value)
# - - string readSetting(string key)
# - - template <typename Type> Type readSetting(string key);
# - -channel settings: (dir and channel args)
# - - ArgInfoList getSettingInfo()
# - - writeSetting(string key, value)
# - - template <typename Type> writeSetting(string key, Type value)
# - - string readSetting(string key)
# - - template <typename Type> Type readSetting(string key)

# Device
#  - has settings
#  - has channels. a channel is identified by a channel number _and_ a direction
#    or a channel has an RX set of settings/gains/etv or a TX set of settings/gains/etc or both
# Channel
# - rx gains: a collection of widgets
# - rx bandwidth: one widget
# - rx settings: a collection of widgets, could be different type of widgets
# - all of the above for tx


class ChannelSettingBase(object):
    def __init__(self,ch,name):
        self.ch=ch
        self.name=name
        self.w=None
        self.value=None
        #self.update()
    def update(self):
        if self.w: self.w.set(self.value)
        return self.value
    def set(self,value):
        self.value=value
    def __str__(self): return "ChannelSettingBase %s" % self.name

class Gain(ChannelSettingBase):
    def __init__(self,ch,name):
        super(Gain,self).__init__(ch,name)
        d=ch.getD()
        ci=ch.getCI()
        grange=ch.dev.getGainRange(d,ci,name)
        self.gmax=grange.maximum()
        self.gmin=grange.minimum()
        self.step=grange.step()
        self.update()
        print(self)
    def update(self):
        self.value=self.ch.dev.getGain(self.ch.d,self.ch.ci,self.name)
        return super(Gain,self).update()
    def set(self,gain):
        super(Gain,self).set(gain)
        self.ch.dev.setGain(self.ch.d,self.ch.ci,self.name,float(gain))
    def __str__(self): return "gain %s(%.1f-%.1f step %.1f): %.1f" % (self.name,self.gmin,self.gmax,self.step,self.value)
    def makeWidget(self,master):
        self.w=Scale(master, from_=self.gmin, to=self.gmax, label=self.name, command=self.set)
        self.w.set(self.value)
        return self.w
    @staticmethod
    def discover(ch):
        dev=ch.getDev()
        d=ch.getD()
        ci=ch.getCI()
        gainnames=dev.listGains(d,ci)
        gains=ch.gains=[]
        for name in gainnames:
            gain=Gain(ch,name)
            gains.append(gain)

class Channel(object):
    def __init__(self,dev,d,ci):
        self.dev=dev
        self.d=d
        self.ci=ci
        self.dt = 'RX' if d==SOAPY_SDR_RX else 'TX'
        self.info=info=dev.getChannelInfo(d,ci)
        print("channel info %s:" % self)
        print(info)
        self.hasAgc=dev.hasGainMode(d,ci)
        Gain.discover(self)
    def setAgc(self,on): self.dev.setGainMode(self.d,self.ci,bool(on))
    def getAgc(self): return dev.getGainMode(self.d,self.ci)
    def getD(self): return self.d
    def getDT(self): return self.dt
    def getCI(self): return self.ci
    def getDev(self): return self.dev
    def __str__(self): return self.dt+str(self.ci)
    @staticmethod
    def discover(dev):
        channels=dev.channels=[];
        channelsbyname=dev.channelsbyname={}
        for d in (SOAPY_SDR_RX,SOAPY_SDR_TX):
            nc=dev.getNumChannels(d);
            for ci in range(nc):
                channel=Channel(dev,d,ci)
                channels.append(channel)
                dt=channel.getDT()
                channelsbyname[dt+str(ci)]=channel



class MyDevice(object):
    def __getattr__(self,name):
        return getattr(self.dev,name)
    def __new__(cls, *args, **kwargs):
        self=object.__new__(cls)
        self.dev=SoapySDR.Device.__new__(SoapySDR.Device,*args,**kwargs)
        return self
    def __init__(self,devspec):
        #super(MyDevice,self).__init__()
        dev=self.dev
        self.devspec=devspec
        self.driverKey=self.getDriverKey()
        self.hardwareKey=self.getHardwareKey()
        Channel.discover(self)
        print(self.channels)
    #def __del__(self):
    #    return self.dev.__del__()

class App:
    
    def __init__(self,master):
        frame=Frame(master)
        frame.pack(fill=X)
        self.qbutt=Button(frame,text="X",command=frame.quit)
        self.qbutt.pack(side=RIGHT)
        self.somebutt=Button(frame,text="butt",command=self.saysomething)
        self.somebutt.pack(side=LEFT)
        contentframe=Frame(master)
        contentframe.pack(fill=BOTH, expand=1)
        tf=contentframe
        objs2update=[]
        for ch in dev.channels:
            Label(tf,text=("Channel %s" % ch)).pack(fill=X)
            for g in ch.gains:
                w=g.makeWidget(tf)
                w.pack(fill=X)
                w.config(orient=HORIZONTAL)
                objs2update.append(g)
        def tick():
            #print("tick!")
            for o in objs2update:
                o.update()
            root.after(500,tick)
        root.after(5000,tick)


    def saysomething(self):
        print("puncifánk")

dev=MyDevice("")
#print(type(dev))
print("driverkey:",dev.driverKey)
print("hardwarekey:",dev.hardwareKey)
#print("hardwarekey:",dev.getHardwareKey())

# - - ArgInfoList getSettingInfo() 
# - - 
# - Antenna TODO
# - - name
# - - setAntenna(name) / getAntenna() returns string
# - Frontend corrections API TODO
# - - bool hasDCOffsetMode()
# - - setDCOffsetMode(bool) sets automatic or none
# - - bool getDCOffsetMode() return current setting
# - - bool hasDCOffset() Does the device support frontend DC offset correction
# - - setDCOffset(complex offset)
# - - complex getDCOffset()
# - - bool hasIQBalance()
# - - setIQBalance(complex balance)
# - - complex getIQBalance
# - - bool hasFrequencyCorrection()
# - - setFrequencyCorrection(double)
# - - double getFrequencyCorrection()
# TODO Frequency api
# TODO Clocking api
# TODO Time API
# TODO Sensor API
# TODO Register API
# TODO GPIO API
# TODO I2C API
# TODO SPI API
# TODO UART API
# 

#print(sdrdev.listAntennas(SOAPY_SDR_RX, 0))
#print(sdrdev.listGains(SOAPY_SDR_RX, 0))
#freqs = sdrdev.getFrequencyRange(SOAPY_SDR_RX, 0)
#for freqRange in freqs: print(freqRange)



root = Tk()
app = App(root)

root.mainloop()
root.destroy()

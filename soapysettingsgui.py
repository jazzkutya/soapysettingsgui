#!/usr/bin/env python3
# -*- coding: utf8 -*-
# vim:fileencoding=utf8

from tkinter import *
import SoapySDR
from SoapySDR import *
import sys
import gc

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

# I removed all parent references toward MyDevice so MyDevice can be
# garbage collected by reference counting.
# Every object that is part of a MyDevice and that needs access to MyDevice
# must inherit from DevAccess, which provides the mechanism for this access.
# The mechanism does not use refs to allow freeing of MyDevice instances,
# but MyDevice class now keeps track of all instances, so destroy() must be
# called on a MyDevice instance to get rid of the reference in the class.
# Objects providing a widget still need to have destroy called on them to get
# rid of the widget object
# these are collected in objs2upate in the App instance
class DevAccess:
    def __init__(self,dev):
        self.dev_id=id(dev)

    def __getattr__(self,name):
        if name=="dev": return MyDevice.get_dev_by_id(self.dev_id)
        return super().__getattr__(name)

class ChannelSettingBase(DevAccess):
    def __init__(self,ch,name):
        super().__init__(ch.dev)
        self.name=name
        self.d=ch.getD()
        self.ci=ch.getCI()
        self.w=None
        self.value=None
    def update(self):
        if self.w: self.w.set(self.value)
        return self.value
    def set(self,value):
        self.value=value
    def __str__(self): return "ChannelSettingBase %s" % self.name
    def destroy(self):
        self.w=None

class Gain(ChannelSettingBase):
    def __init__(self,ch,name):
        super().__init__(ch,name)
        grange=self.dev.getGainRange(self.d,self.ci,name)
        self.gmax=grange.maximum()
        self.gmin=grange.minimum()
        self.step=grange.step()
        self.update()
        print(self)
    def update(self):
        self.value=self.dev.getGain(self.d,self.ci,self.name)
        return super().update()
    def set(self,gain):
        self.dev.setGain(self.d,self.ci,self.name,float(gain))
        self.update()
    def __str__(self): return "gain %s(%.1f-%.1f step %.1f): %.1f" % (self.name,self.gmin,self.gmax,self.step,self.value)
    def makeWidget(self,master):
        self.w=Scale(master, from_=self.gmin, to=self.gmax, label=self.name, command=app.soapywrapper(self.set))
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

class Channel(DevAccess):
    def __init__(self,dev,d,ci):
        super().__init__(dev)
        self.d=d
        self.ci=ci
        self.dt = 'RX' if d==SOAPY_SDR_RX else 'TX'
        self.info=info=dev.getChannelInfo(d,ci)
        print("channel info %s:" % self)
        print(info)
        self.hasAgc=dev.hasGainMode(d,ci)
        Gain.discover(self)
    def setAgc(self,on): self.dev.setGainMode(self.d,self.ci,bool(on))
    def getAgc(self): return self.dev.getGainMode(self.d,self.ci)
    def getD(self): return self.d   # direction
    def getDT(self): return self.dt # direction as text
    def getCI(self): return self.ci # channel index
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
    def destroy(self): pass

class MyDevice(object):
    mydevs={}
    @staticmethod
    def get_dev_by_id(dev_id):
        return MyDevice.mydevs[dev_id]
    def __getattr__(self,name):
        return getattr(self.dev,name)
    def __new__(cls, *args, **kwargs):
        self=object.__new__(cls)
        object.__setattr__(self,'dev',SoapySDR.Device.__new__(SoapySDR.Device,*args,**kwargs))
        return self
    def __init__(self,devspec):
        MyDevice.mydevs[id(self)]=self
        #super(MyDevice,self).__init__() # stupid things throws an error instead of a simple pass
        dev=self.dev
        self.devspec=devspec
        self.driverKey=self.getDriverKey()
        self.hardwareKey=self.getHardwareKey()
    def discover(self):
        Channel.discover(self)
        print(self.channels)
    def destroy(self):
        dev_id=id(self)
        self.channelsbyname=None
        self.channels=None
        if dev_id in MyDevice.mydevs: del MyDevice.mydevs[id(self)]

    def __del__(self):
        print("MyDevice is being destructed")
        self.destroy()
        try: object.__getattribute__(self,'dev').__del__
        except AttributeError: pass

class App:
    
    def __init__(self,master):
        self.timer=None
        frame=Frame(master)
        frame.pack(fill=X)
        self.qbutt=Button(frame,text="X",command=frame.quit)
        self.qbutt.pack(side=RIGHT)
        self.rcbutt=Button(frame,text="connect",command=self.buildSDRgui,state=DISABLED)
        self.rcbutt.pack(side=LEFT)
        self.contentframe=Frame(master)
        self.contentframe.pack(fill=BOTH, expand=1)
        self.objs2update=[]
    def buildSDRgui(self):
        self.dev=MyDevice("driver=remote,remote=localhost")
        self.rcbutt.config(state=DISABLED)
        print("driverkey:",self.dev.driverKey)
        print("hardwarekey:",self.dev.hardwareKey)
        self.dev.discover()
        contentframe=self.contentframe
        tf=contentframe
        objs2update=self.objs2update=[]
        for ch in self.dev.channels:
            Label(tf,text=("Channel %s" % ch)).pack(fill=X)
            for g in ch.gains:
                w=g.makeWidget(tf)
                w.pack(fill=X)
                w.config(orient=HORIZONTAL)
                objs2update.append(g)
        self=self
        def tick():
            self.timer=None
            #print("tick!")
            for o in objs2update: o.update()
            self.timer=root.after(500,self.tickcb)
        self.tickcb=self.soapywrapper(tick)
        self.timer=root.after(5000,self.tickcb)

    def destroySDRgui(self):
        if self.timer: root.after_cancel(self.timer)
        self.timer=None
        self.dev.destroy()
        del(self.dev)
        self.dev=None
        for o in self.objs2update: o.destroy()
        self.objs2update=[]
        for w in self.contentframe.winfo_children(): w.destroy()
        gc.collect()
        self.rcbutt.config(state=NORMAL)

    def saysomething(self):
        print("puncifánk")
    def soapywrapper(self,call):
        self=self
        call=call
        def f(*args, **kwargs):
            try:
                call(*args,**kwargs)
            except RuntimeError as e:
                errmsg=str(e)
                print("Exception: ",errmsg)
                if 'Soapy' in errmsg:
                    self.destroySDRgui()
                else: raise
        return f


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


def scalewheel(ev):
    #print("handling event type {}, x {}, y {} widget {}".format(ev.type,ev.x,ev.y,ev.widget.__class__))
    w=ev.widget
    if isinstance(w, Scale):
        d=0
        if int(ev.type)==38: d=ev.delta/abs(ev.delta)
        if int(ev.type)==4 and ev.num==4: d=1
        if int(ev.type)==4 and ev.num==5: d=-1
        w.set(w.get()+d)

root = Tk()
app = App(root)
app.buildSDRgui()
#print(type(dev))
#print("hardwarekey:",dev.getHardwareKey())


root.bind("<Button-4>",scalewheel)
root.bind("<Button-5>",scalewheel)
root.bind("<MouseWheel>",scalewheel)

root.mainloop()
root.destroy()

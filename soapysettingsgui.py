#!/usr/bin/env python3
# -*- coding: utf8 -*-
# vim:fileencoding=utf8

import tkinter as tk
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
# - - SoapySDR.ArgInfoList getSettingInfo() // returns a list of argument info structures. NO direction and channel argument!
# - - writeSetting(string key, value)
# - - template <typename Type> writeSetting(string key, Type &value)
# - - string readSetting(string key)
# - - template <typename Type> Type readSetting(string key);
# - -channel settings: (dir and channel args)
# - - SoapySDR.ArgInfoList getSettingInfo()
# - - writeSetting(string key, value)
# - - template <typename Type> writeSetting(string key, Type value)
# - - string readSetting(string key)
# - - template <typename Type> Type readSetting(string key)
# - - 

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
        raise AttributeError(name)

class DeviceSetting(DevAccess):
    def __init__(self,dev,arginfo):
        super().__init__(dev)
        self.valid=False
        self.key=self.name=arginfo.key
        if arginfo.name: self.name=arginfo.name
        self.description=""
        if arginfo.description: self.description=arginfo.description
        #self.value=arginfo.value  # we'll use update instead to initialize value
        self.type=arginfo.type
        self.cv=None
        self.w=None
        self.value=None
        if self.type==SoapySDR.ArgInfo.BOOL:
            self.getter=self.dev.readSettingBool
            self.valid=True
        elif self.type==SoapySDR.ArgInfo.INT:
            if arginfo.range:
                self.vstep=1
                self.vmin=arginfo.range.minimum()
                self.vmax=arginfo.range.maximum()
                if int(arginfo.range.step()): self.vstep=int(arginfo.range.step())
                self.getter=self.dev.readSettingInt
                self.valid=True
            else: print("int without range unsupported")
        elif self.type==SoapySDR.ArgInfo.FLOAT:
            if arginfo.range:
                self.vstep=1.0
                self.vmin=arginfo.range.minimum()
                self.vmax=arginfo.range.maximum()
                if arginfo.range.step(): self.vstep=arginfo.range.step()
                self.getter=self.dev.readSettingFloat
                self.valid=True
            else: print("float without range unsupported")
        elif self.type==SoapySDR.ArgInfo.STRING:
            if arginfo.options:
                self.values = list(arginfo.options)
                self.getter=self.dev.readSetting
                self.valid=True
            else: print("string without option list unsupported")
        else:
            raise RuntimeError("Unknown SoapySDR.ArgInfo type: "+self.type)

        if self.valid: self.update()
        #print(self)
    def update(self):
        self.value=self.getter(self.key)
        #print("{} from device: {}({})".format(self.key,type(self.value),self.value))
        if self.cv: self.cv.set(self.value)
        if self.type in (SoapySDR.ArgInfo.INT,SoapySDR.ArgInfo.FLOAT) and self.w: self.w.set(self.value)
        return self.value
    def set(self,*args):
        if self.type==SoapySDR.ArgInfo.BOOL:
            if int(self.cv.get())!=int(self.value):
                print("setting",self.key,"to",bool(self.cv.get()))
                self.dev.writeSetting(self.key,bool(self.cv.get()))
        elif self.type==SoapySDR.ArgInfo.INT:
            self.dev.writeSetting(self.key,int(args[0]))
        elif self.type==SoapySDR.ArgInfo.FLOAT:
            self.dev.writeSetting(self.key,float(args[0]))
        elif self.type==SoapySDR.ArgInfo.STRING:
            if self.cv.get()!=self.value:
                self.dev.writeSetting(self.key,self.cv.get())
        else: raise RuntimeError("meh")
        self.update()
    def __str__(self): return "channel %s %s" % (self.chname,self.name)
    def makeWidget(self,master):
        if self.type==SoapySDR.ArgInfo.BOOL:
            cv=self.cv=tk.IntVar()
            cv.set(self.value)
            cv.trace("w",app.soapywrapper(self.set))
            self.w=tk.Checkbutton(master, variable=cv)
            return self.w
        elif self.type in (SoapySDR.ArgInfo.INT,SoapySDR.ArgInfo.FLOAT):
            self.w=tk.Scale(master, from_=self.vmin, to=self.vmax, command=app.soapywrapper(self.set))
            self.w.config(orient=tk.HORIZONTAL)
            self.w.set(self.value)
            return self.w
        elif self.type==SoapySDR.ArgInfo.STRING:
            cv=self.cv=tk.StringVar()
            cv.set(self.value)
            cv.trace("w",app.soapywrapper(self.set))
            self.w=tk.OptionMenu(master, cv, *self.values)
            return self.w
        else: raise RuntimeError("meh")
    def destroy(self):
        self.w=None
        self.cv=None
    @staticmethod
    def discover(dev):
        arginfos=dev.getSettingInfo()
        settings=dev.settings=[]
        for arginfo in arginfos:
            setting=DeviceSetting(dev,arginfo)
            if setting.valid: settings.append(setting)

class ChannelSettingBase(DevAccess):
    def __init__(self,ch,name=None):
        super().__init__(ch.dev)
        self.name=name
        self.d=ch.getD()
        self.ci=ch.getCI()
        self.w=None
        self.cv=None
        self.value=None
    def set(self,value):
        self.value=value
    def __str__(self): return "ChannelSettingBase %s" % self.name
    def destroy(self):
        self.w=None
        self.cv=None

class Bandwidth(ChannelSettingBase):
    def __init__(self,ch):
        super().__init__(ch,"Bandwidth")
        self.chname=str(ch)
        self.bwmin,self.bwmax=None,None
        self.values=None
        ranges=self.dev.getBandwidthRange(self.d,self.ci)
        self.valid=True
        if len(ranges)>1:
            self.values=[]
            for r in ranges:
                if r.minimum()!=r.maximum(): print("This device has a very complicated bandwidth setting!")
                self.values.append((r.minimum()+r.maximum())/2)
        elif len(ranges)==1:
            self.bwmin=ranges[0].minimum()
            self.bwmax=ranges[0].maximum()
        else: self.valid=False
        if self.valid: self.update()
        print(self)
    def update(self):
        self.value=self.dev.getBandwidth(self.d,self.ci)
        if self.cv: self.cv.set(self.value)
        if self.bwmin and self.w: self.w.set(self.value)
        return self.value
    def set(self,*args):
        if self.bwmin: self.dev.setBandiwdth(self.d,self.ci,float(args[0]))
        else:
            if float(self.cv.get())!=self.value:
                #print("setting bandwidth because",self.cv.get(),"!=",self.value)
                #print("setting bandwidth to",float(self.cv.get()))
                self.dev.setBandwidth(self.d,self.ci,float(self.cv.get()))
        self.update()
    def __str__(self): return "channel %s bandwidth" % (self.chname)
    def makeWidget(self,master):
        if self.bwmin:
            self.w=tk.Scale(master, from_=self.bwmin, to=self.bwmax, command=app.soapywrapper(self.set))
            self.w.set(self.value)
        else:
            cv=self.cv=tk.StringVar()
            cv.set(self.value)
            cv.trace("w",app.soapywrapper(self.set))
            self.w=tk.OptionMenu(master, cv, *self.values)
        return self.w
    @staticmethod
    def discover(ch):
        ch.bandwidth=Bandwidth(ch)
        if not ch.bandwidth.valid: ch.bandwidth=None

class Antenna(ChannelSettingBase):
    def __init__(self,ch):
        super().__init__(ch,"Antenna")
        self.chname=str(ch)
        self.values=self.dev.listAntennas(self.d,self.ci)
        if self.values and len(self.values)>0: self.update()
        print(self)
    def update(self):
        self.value=self.dev.getAntenna(self.d,self.ci)
        #print("setting antenna value to",self.value)
        if self.cv: self.cv.set(self.value)
        return self.value
    def set(self,*args):
        if self.cv.get()!=self.value:
            self.dev.setAntenna(self.d,self.ci,self.cv.get())
            self.update()
    def __str__(self): return "channel %s antenna" % (self.chname)
    def makeWidget(self,master):
        cv=self.cv=tk.StringVar()
        cv.set(self.value)
        cv.trace("w",app.soapywrapper(self.set))
        self.w=tk.OptionMenu(master, cv, *self.values)
        return self.w
    @staticmethod
    def discover(ch):
        ch.antenna=Antenna(ch)
        if (not(ch.antenna.values) or len(ch.antenna.values)<1): ch.antenna=None

class AGC(ChannelSettingBase):
    def __init__(self,ch):
        super().__init__(ch,"AGC")
        self.chname=str(ch)
        self.valid=self.dev.hasGainMode(self.d,self.ci)
        if self.valid: self.update()
    def update(self):
        self.value=self.dev.getGainMode(self.d,self.ci)
        if self.cv: self.cv.set(self.value)
        return self.value
    def set(self,*args):
        if self.cv.get()!=self.value:
            self.dev.setGainMode(self.d,self.ci,bool(self.cv.get()))
            self.update()
    def __str__(self): return "channel %s AGC" % (self.chname)
    def makeWidget(self,master):
        cv=self.cv=tk.IntVar()
        cv.set(self.value)
        cv.trace("w",app.soapywrapper(self.set))
        self.w=tk.Checkbutton(master, variable=cv)
        return self.w
    @staticmethod
    def discover(ch):
        ch.agc=AGC(ch)
        if not ch.agc.valid: ch.agc=None

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
        if self.w: self.w.set(self.value)
        return self.value
    def set(self,gain):
        self.dev.setGain(self.d,self.ci,self.name,float(gain))
        self.update()
    def __str__(self): return "gain %s(%.1f-%.1f step %.1f): %.1f" % (self.name,self.gmin,self.gmax,self.step,self.value)
    def makeWidget(self,master):
        self.w=tk.Scale(master, from_=self.gmin, to=self.gmax, label=self.name, command=app.soapywrapper(self.set))
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
        print('antenna list:',dev.listAntennas(d,ci))
        self.hasAgc=dev.hasGainMode(d,ci)
        Gain.discover(self)
        Antenna.discover(self)
        AGC.discover(self)
        Bandwidth.discover(self)
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
        dev=super().__getattribute__('dev')
        if dev: return getattr(self.dev,name)
        raise AttributeError()
    def __new__(cls, *args, **kwargs):
        self=object.__new__(cls)
        object.__setattr__(self,'dev',SoapySDR.Device.__new__(SoapySDR.Device,*args,**kwargs))
        return self
    def __init__(self,devspec):
        self.mydevs[id(self)]=self
        super().__init__()
        dev=self.dev
        self.devspec=devspec
        self.driverKey=self.getDriverKey()
        self.hardwareKey=self.getHardwareKey()
    def discover(self):
        Channel.discover(self)
        DeviceSetting.discover(self)
        print(self.channels)
    def destroy(self):
        dev_id=id(self)
        self.channelsbyname=None
        self.channels=None
        self.dev.close()
        if dev_id in self.mydevs: del self.mydevs[id(self)]

    def __del__(self):
        print("MyDevice is being destructed")
        self.destroy()
        try: object.__getattribute__(self,'dev').__del__
        except AttributeError: pass

class App:
    
    def __init__(self,master):
        self.timer=None
        frame=tk.Frame(master,borderwidth=2,relief=tk.RIDGE)
        frame.grid(sticky=tk.W+tk.E)
        self.rcbutt=tk.Button(frame,text="connect",command=self.buildSDRgui,state=tk.DISABLED)
        self.rcbutt.grid(row=0,sticky=tk.W)
        #Label(frame,text="STUFF").grid(column=1,row=0)
        self.qbutt=tk.Button(frame,text="X",command=frame.quit)
        self.qbutt.grid(column=10,row=0,sticky=tk.E)
        self.contentframe=tk.Frame(master)
        self.contentframe.grid(row=1,sticky=tk.N+tk.E+tk.W+tk.S)
        self.objs2update=[]
    def buildSDRgui(self):
        self.dev=MyDevice("driver=remote,remote=localhost")
        self.rcbutt.config(state=tk.DISABLED)
        print("driverkey:",self.dev.driverKey)
        print("hardwarekey:",self.dev.hardwareKey)
        self.dev.discover()
        contentframe=self.contentframe
        tf=contentframe
        tk.Label(tf,text="device").grid(column=0,row=0)
        objs2update=self.objs2update=[]
        rowcnt=1
        for o in self.dev.settings:
            frame=tk.Frame(tf)
            tk.Label(frame,text=o.name).grid(column=0,sticky=tk.W)
            w=o.makeWidget(frame)
            w.grid(column=1,row=0,sticky=tk.E)
            objs2update.append(o)
            frame.grid(column=0,row=rowcnt,sticky=tk.W+tk.E)
            rowcnt=rowcnt+1
        chcnt=0
        for ch in self.dev.channels:
            tk.Label(tf,text=("channel %s" % ch)).grid(column=1+chcnt,row=0)
            rowcnt=1
            for o in ch.antenna,ch.agc,ch.bandwidth:
                if o:
                    frame=tk.Frame(tf)
                    tk.Label(frame,text=o.name).grid(column=0)
                    w=o.makeWidget(frame)
                    w.grid(column=1,row=0,sticky=tk.W)
                    objs2update.append(o)
                    frame.grid(column=1+chcnt,row=rowcnt,sticky=tk.W+tk.E)
                    rowcnt=rowcnt+1
            for g in ch.gains:
                w=g.makeWidget(tf)
                w.config(orient=tk.HORIZONTAL)
                w.grid(column=1+chcnt,row=rowcnt,sticky=tk.W+tk.E)
                objs2update.append(g)
                rowcnt=rowcnt+1
            chcnt=chcnt+1
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
        self.rcbutt.config(state=tk.NORMAL)

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
    if isinstance(w, tk.Scale):
        d=0
        if int(ev.type)==38: d=ev.delta/abs(ev.delta)
        if int(ev.type)==4 and ev.num==4: d=1
        if int(ev.type)==4 and ev.num==5: d=-1
        w.set(w.get()+d)

root = tk.Tk()
app = App(root)
app.buildSDRgui()
#print(type(dev))
#print("hardwarekey:",dev.getHardwareKey())


root.bind("<Button-4>",scalewheel)
root.bind("<Button-5>",scalewheel)
root.bind("<MouseWheel>",scalewheel)

root.mainloop()
root.destroy()

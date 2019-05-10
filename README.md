# soapysettingsgui

# What?

SDR Settings GUI for SoapySDR.

# Why?

When you use an SDR Program(tm) that does not allow you to set all device settings of your SDR Device(tm), you can use this. Or not. This is still early stage, testing and feedback needed badly.

# OK...

To use this simultaneously with the SDR Program(tm) you have to share the device with [SoapyRemote](https://github.com/pothosware/SoapyRemote). Start SoapySDRServer on the computer you have your SDR Device(tm) attached to. Point your SDR Program(tm) to your running SoapySDRServer. Start soapysettingsgui.py specifying the same SoapySDRServer:

```
./soapysettingsgui.py device=remote,remote=192.168.1.1
```

Use the IP address of your machine running SoapySDRServer. If it's the same machine you could use remote=localhost, but this is the default (driver=remote,remote=localhost) so just start soapysettingsgui.py.

To share the device when using linrad on linux you can also use [this](https://github.com/jazzkutya/linrad_extio_SoapySDR). It has an embedded SoapySDR exactly for this usage, avoiding network overhead for the IQ stream.

## Other notes

When building SoapySDR you need swig newer than 3.0 for the python bindings. Ubuntu 14.04 has swig 3.0 but the package name is called swig3.0 and by default an earlier version is installed.

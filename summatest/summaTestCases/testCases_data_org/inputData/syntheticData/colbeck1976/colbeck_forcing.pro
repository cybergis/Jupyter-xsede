pro colbeck_forcing

; define constants
Tfreeze = 273.16d

; define parameters
dt = 60.d ; (time step)

; define plotting parameters
window, 0, xs=1000, ys=1000, retain=2
device, decomposed=0
LOADCT, 39
!P.BACKGROUND=255
!P.CHARSIZE=2.5
!P.COLOR=0
erase, color=255
!P.MULTI=[0,1,4]

; define the number of days
ndays = 3

; define the number of time steps per hour
nprhr = 3600.d/dt

; define the number of steps per day
nprdy = 86400.d/dt

; define the number of time steps
ntime = ndays*nprdy

; define time in seconds
stime = (dindgen(ntime)+1.d)*dt

; define time in hours
htime = stime/3600.

; define maximum radiation
rdmax = 250.d

; define the dayln parameter
dayln = -0.1

; define radiation index
radix = cos(2.d*!pi * (htime/24.d) + !pi) + dayln

; define radiation
swrad = replicate(0.d, ntime)  ;radix*(rdmax / (1.+dayln))

; set negative radiation to zero
ibad = where(swrad le 0.d, nbad)
if (nbad gt 0) then swrad[ibad] = 0.d

; make a base plot for solar radiation
plot, htime, xrange=[0,ntime/nprhr], yrange=[0,1000], xstyle=9, ystyle=1, $
 ytitle = 'Solar radiation (W m!e-2!n)', xmargin=[10,10], ymargin=[3,2], $
 xticks=6, /nodata
plots, [htime[0],htime[ntime-1]], [  0,  0]
plots, [htime[0],htime[ntime-1]], [250,250]

plots, [24,24], [0,250]
plots, [48,48], [0,250]

oplot, htime, swrad

; define other forcing variables
lwrad = 275.d
awind =   0.d
atemp = Tfreeze + 10.d
sphum = 1.d-3
apres = 101325.d

; define precipitation
aprcp = replicate(0.d, ntime)

; define time less than 3 hours
aprcp[where(stime le 10800.d)] = 10.d^(-2.d)

; define time
atime = stime/86400.d + julday(1,1,2000,0,0,0.d)

; define file
filename = 'colbeck1976_forcing'

; open NetCDF file for definition
ncid = ncdf_create(filename+'.nc', /clobber)
ncdf_control, ncid

; define dimensions in the NetCDF file
idHRU  = ncdf_dimdef(ncid, 'hru', 1)
idTime = ncdf_dimdef(ncid, 'time', /unlimited)

; define the hru ID
ivar_id = ncdf_vardef(ncid, 'hruId', [idHRU], /long) 

; define the latitude and longitude
ivar_id = ncdf_vardef(ncid, 'latitude', [idHRU], /double)
ivar_id = ncdf_vardef(ncid, 'longitude', [idHRU], /double)

; define the data step and time
ivar_id = ncdf_vardef(ncid, 'data_step', /double)
ivar_id = ncdf_vardef(ncid, 'time', [idTime], /double)

; define the time units
ncdf_attput, ncid, ivar_id, 'units', "seconds since 1990-01-01 00:00:00", /char

; define forcing variables
cVar = ['LWRadAtm','SWRadAtm','airpres','airtemp','pptrate','spechum','windspd']
for ivar=0,n_elements(cVar)-1 do begin
 ivar_id = ncdf_vardef(ncid, cvar[ivar], [idHRU, idTime], /double)
endfor

; exit control mode
ncdf_control, ncid, /endef

; write the metadata
ncdf_varput, ncid, ncdf_varid(ncid,'hruId'), 1001
ncdf_varput, ncid, ncdf_varid(ncid,'latitude'), 40.d
ncdf_varput, ncid, ncdf_varid(ncid,'longitude'), 250.d
ncdf_varput, ncid, ncdf_varid(ncid,'data_step'), dt

; make a forcing file
openw, out_unit, filename+'.txt', /get_lun

; loop through time
for itime=0,ntime-1 do begin

 ; define date
 caldat, atime[itime], im, id, iyyy, ih, imi, dsec

 ; write time to the NetCDF file
 ncdf_varput, ncid, ncdf_varid(ncid,'time'), stime[itime], offset=itime, count=1

 ; print synthetic "data" to the netCDF file
 for ivar=0,n_elements(cVar)-1 do begin
  ivar_id = ncdf_varid(ncid,cvar[ivar])
  case cvar[ivar] of
   'pptrate':  ncdf_varput, ncid, ivar_id, aprcp[itime], offset=[0,itime], count=[1,1]
   'airtemp':  ncdf_varput, ncid, ivar_id, atemp,        offset=[0,itime], count=[1,1]
   'airpres':  ncdf_varput, ncid, ivar_id, apres,        offset=[0,itime], count=[1,1]
   'spechum':  ncdf_varput, ncid, ivar_id, sphum,        offset=[0,itime], count=[1,1]
   'windspd':  ncdf_varput, ncid, ivar_id, awind,        offset=[0,itime], count=[1,1]
   'SWRadAtm': ncdf_varput, ncid, ivar_id, swrad[itime], offset=[0,itime], count=[1,1]
   'LWRadAtm': ncdf_varput, ncid, ivar_id, lwrad,        offset=[0,itime], count=[1,1]
   else: stop, 'unable to identify variable'
  endcase
 endfor  ; looping through variables

 ; print synthetic "data" to the ASCII file
 printf, out_unit, iyyy, im, id, ih, imi, dsec, aprcp[itime], swrad[itime], lwrad, atemp, awind, apres, sphum, $
  format='(i4,1x,4(i2,1x),f6.1,1x,e14.4,1x,5(f10.3,1x),e12.3)'

endfor ; looping through time

; free up file unit
free_lun, out_unit
ncdf_close, ncid

stop
end

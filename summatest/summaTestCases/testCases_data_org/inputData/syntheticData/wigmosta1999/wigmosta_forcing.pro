pro wigmosta_forcing

; define constants
Tfreeze = 273.16d

; define parameters
dt = 3600.d ; (time step)

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
ndays = 42

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

; define forcing variables
swrad = 100.d
lwrad = 350.d
awind =   0.d
sphum = 1.d-3
apres = 101325.d
atemp = 273.16d + 10.d

; define precipitation
aPrcp = dblarr(ntime)

; define the precipitation
iRain = where(htime le 550.d, complement=iDry)
aPrcp[iRain] = 20.d/3600.d  ; 20 mm/hour
aPrcp[iDry]  = 0.d

; define time
atime = stime/86400.d + julday(1,1,2000,0,0,0.d)

; make a forcing file
openw, out_unit, 'wigmosta_forcing-exfiltrate.txt', /get_lun

for itime=0,ntime-1 do begin
 ; define date
 caldat, atime[itime], im, id, iyyy, ih, imi, dsec
 ; print synthetic "data"
 printf, out_unit, iyyy, im, id, ih, imi, dsec, aprcp[itime], swrad, lwrad, atemp, awind, apres, sphum, $
  format='(i4,1x,4(i2,1x),f6.1,1x,e14.6,1x,5(f10.3,1x),e12.3)'
endfor

; free up file unit
free_lun, out_unit


stop
end

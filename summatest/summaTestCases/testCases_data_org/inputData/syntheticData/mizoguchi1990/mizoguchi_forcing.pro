pro mizoguchi_forcing

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
atemp = Tfreeze - 6.d
sphum = 1.d-3
apres = 101325.d

; define precipitation
aprcp = replicate(0.d, ntime)

; define time
atime = stime/86400.d + julday(1,1,2000,0,0,0.d)

; make a forcing file
openw, out_unit, 'mizoguchi_forcing.txt', /get_lun

for itime=0,ntime-1 do begin
 ; define date
 caldat, atime[itime], im, id, iyyy, ih, imi, dsec
 ; print synthetic "data"
 printf, out_unit, iyyy, im, id, ih, imi, dsec, aprcp[itime], swrad[itime], lwrad, atemp, awind, apres, sphum, $
  format='(i4,1x,4(i2,1x),f6.1,1x,e14.4,1x,5(f10.3,1x),e12.3)'
endfor

; free up file unit
free_lun, out_unit


stop
end

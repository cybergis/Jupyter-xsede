pro wigmosta_icond

; used to create initial conditions for the synthetic test case

; define vGn parameters (used to compute volumetric liquid water content)
alpha     =  -0.5d     ; m-1
n         =   1.5d
m         =   1.d - 1.d/n
theta_sat =   0.35d
theta_res =   0.1d
k_sat     =   0.00000075d
f_impede  = -15.d

; define the number of nodes
nodes = 8

; define soil depth (m)
zsoil = 1.5d

; define layer thickness
z_lay = zsoil/double(nodes)

; define vertical grid (m) -- positive downward
z_dep = (dindgen(nodes+1)/double(nodes))*zsoil

; define the mid-point of each layer
z_m = (z_dep[0:nodes-1] + z_dep[1:nodes])/2.d

; define the layer thickness
z_i = z_dep[1:nodes] - z_dep[0:nodes-1]

; define arrays
zpress = replicate(-50000.d, nodes)
z_temp = replicate(283.16d,nodes)
ztheta = dblarr(nodes)

for ilayer=0,nodes-1 do begin
 ztheta[ilayer] = call_function('theta', zpress[ilayer], alpha, theta_res, theta_sat, n, m)
endfor

; write data to file
openw, out_unit, 'wigmosta_icond.txt', /get_lun
 for ilayer=0,nodes-1 do begin
  printf, out_unit, 'soil', z_m[ilayer]-0.5d*z_i[ilayer], z_i[ilayer], $
   z_temp[ilayer], 0.d,  ztheta[ilayer], zpress[ilayer], $
   format='(a10,1x,2(f12.7,1x),f10.3,1x,f17.6,1x,f16.6,1x,f16.6)'
 endfor
free_lun, out_unit


stop
end

; *****************************************************************************************************************
; *****************************************************************************************************************

function k_psi, psi, alpha, k_sat, n, m

; computes hydraulic conductivity given psi and soil hydraulic parameters alpha, k_sat, n, and m
;  psi     = pressure (m)
;  alpha   = scaling parameter (m-1)
;  k_sat   = saturated hydraulic conductivity (m s-1)
;  n       = vGn "n" parameter
;  m       = vGn "m" parameter

work = dblarr(n_elements(psi))

ineg = where(psi lt 0.d, nneg, complement=ipos, ncomplement=npos)
if (nneg gt 0) then work[ineg] = k_sat * $
 ( ( (1.d - (psi[ineg]*alpha)^(n-1.d) * (1.d + (psi[ineg]*alpha)^n)^(-m))^2.d ) / ( (1.d + (psi[ineg]*alpha)^n)^(m/2.d) ) )
if (npos gt 0) then work[ipos] = k_sat

return, work

end

; *****************************************************************************************************************
; *****************************************************************************************************************

function theta, psi, alpha, theta_res, theta_sat, n, m

; computes volumetric water content based on psi and soil hydraulic parameters alpha, n, and m

;  psi       = pressure (m)
;  alpha     = scaling parameter (m-1)
;  theta_res = residual volumetric water content (-)
;  theta_sat = porosity (-)
;  n         = vGn "n" parameter
;  m         = vGn "m" parameter

work = dblarr(n_elements(psi))

ineg = where(psi lt 0.d, nneg, complement=ipos, ncomplement=npos)
if (nneg gt 0) then work[ineg] = theta_res + (theta_sat - theta_res)*(1.d + (alpha*psi[ineg])^n)^(-m)
if (npos gt 0) then work[ipos] = theta_sat

return, work

end

; *****************************************************************************************************************
; *****************************************************************************************************************

function dTheta_dPsi, psi, alpha, theta_res, theta_sat, n, m

; computes the soil moisture capacity function, dTheta_dPsi (m-1)

;  psi       = pressure (m)
;  alpha     = scaling parameter (m-1)
;  theta_res = residual volumetric water content (-)
;  theta_sat = porosity (-)
;  n         = vGn "n" parameter
;  m         = vGn "m" parameter

work = dblarr(n_elements(psi))

ineg = where(psi lt 0.d, nneg, complement=ipos, ncomplement=npos)
if (nneg gt 0) then work[ineg] = (theta_sat-theta_res) * $
                      (-m*(1.d + (psi[ineg]*alpha)^n)^(-m-1.d)) * n*(psi[ineg]*alpha)^(n-1.d) * alpha
if (npos gt 0) then work[ipos] = 0.d

return, work

end

; *****************************************************************************************************************
; *****************************************************************************************************************

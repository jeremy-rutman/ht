# -*- coding: utf-8 -*-
'''Chemical Engineering Design Library (ChEDL). Utilities for process modeling.
Copyright (C) 2016, Caleb Bell <Caleb.Andrew.Bell@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''

from __future__ import division
from math import pi, log10
from scipy.constants import g
from scipy.optimize import newton, fsolve
from fluids.core import Prandtl, Boiling, Bond, Weber, nu_mu_converter
from ht.conv_internal import turbulent_Gnielinski

__all__ = ['Thome', 'Lazarek_Black', 'Li_Wu', 'Sun_Mishima', 'Yun_Heo_Kim']


def Lazarek_Black(m, D, mul, kl, Hvap, q=None, Te=None):
    r'''Calculates heat transfer coefficient for film boiling of saturated
    fluid in vertical tubes for either upward or downward flow. Correlation
    is as shown in [1]_, and also reviewed in [2]_ and [3]_.
    
    Either the heat flux or excess temperature is required for the calculation
    of heat transfer coefficient.
    
    Quality independent. Requires no properties of the gas.
    Uses a Reynolds number assuming all the flow is liquid.

    .. math::
        h_{tp} = 30 Re_{lo}^{0.857} Bg^{0.714} \frac{k_l}{D}
        
        Re_{lo} = \frac{G_{tp}D}{\mu_l}
    
    Parameters
    ----------
    m : float
        Mass flow rate [kg/s]
    D : float
        Diameter of the channel [m]
    mul : float
        Viscosity of liquid [Pa*s]
    kl : float
        Thermal conductivity of liquid [W/m/K]
    Hvap : float
        Heat of vaporization of liquid [J/kg]
    q : float, optional
        Heat flux to wall [W/m^2]
    Te : float, optional
        Excess temperature of wall, [K]

    Returns
    -------
    h : float
        Heat transfer coefficient [W/m^2/K]

    Notes
    -----
    [1]_ has been reviewed. The code to derive the form with `Te` specified is
    as follows:
    
    >>> from sympy import *
    >>> Relo, Bgish, kl, D, h, Te = symbols('Relo, Bgish, kl, D, h, Te',
    ... positive=True, real=True)
    >>> solve(Eq(h, 30*Relo**Rational(857,1000)*(Bgish*h*Te)**Rational(714,
    ... 1000)*kl/D), h)
    [27000*30**(71/143)*Bgish**(357/143)*Relo**(857/286)*Te**(357/143)*kl**(500/143)/D**(500/143)]

    [2]_ claims it was developed for a range of quality 0-0.6,
    Relo 860-5500, mass flux 125-750 kg/m^2/s, q of 1.4-38 W/cm^2, and with a
    pipe diameter of 3.1 mm. Developed with data for R113 only.

    Examples
    --------
    >>> Lazarek_Black(m=10, D=0.3, mul=1E-3, kl=0.6, Hvap=2E6, Te=100)
    9501.932636079293

    References
    ----------
    .. [1] Lazarek, G. M., and S. H. Black. "Evaporative Heat Transfer, 
       Pressure Drop and Critical Heat Flux in a Small Vertical Tube with 
       R-113." International Journal of Heat and Mass Transfer 25, no. 7 (July 
       1982): 945-60. doi:10.1016/0017-9310(82)90070-9.
    .. [2] Fang, Xiande, Zhanru Zhou, and Dingkun Li. "Review of Correlations 
       of Flow Boiling Heat Transfer Coefficients for Carbon Dioxide."
       International Journal of Refrigeration 36, no. 8 (December 2013): 
       2017-39. doi:10.1016/j.ijrefrig.2013.05.015.
    .. [3] Bertsch, Stefan S., Eckhard A. Groll, and Suresh V. Garimella. 
       "Review and Comparative Analysis of Studies on Saturated Flow Boiling in
       Small Channels." Nanoscale and Microscale Thermophysical Engineering 12,
       no. 3 (September 4, 2008): 187-227. doi:10.1080/15567260802317357.
    '''
    G = m/(pi/4*D**2)
    Relo = G*D/mul
    if q:
        Bg = Boiling(G=G, q=q, Hvap=Hvap)
        htp = 30*Relo**0.857*Bg**0.714*kl/D
    elif Te:
        # Solved with sympy
        htp = 27000*30**(71/143)*(1./(G*Hvap))**(357/143)*Relo**(857/286)*Te**(357/143)*kl**(500/143)/D**(500/143)
    else:
        raise Exception('Either q or Te is needed for this correlation')
    return htp


def Li_Wu(m, x, D, rhol, rhog, mul, kl, Hvap, sigma, q=None, Te=None):
    r'''Calculates heat transfer coefficient for film boiling of saturated
    fluid in any orientation of flow. Correlation
    is as shown in [1]_, and also reviewed in [2]_ and [3]_.
    
    Either the heat flux or excess temperature is required for the calculation
    of heat transfer coefficient. Uses liquid Reynolds number, Bond number,
    and Boiling numer.
    
    .. math::
        h_{tp} = 334 Bg^{0.3}(Bo\cdot Re_l^{0.36})^{0.4}\frac{k_l}{D}
        
        Re_{l} = \frac{G(1-x)D}{\mu_l}
    
    Parameters
    ----------
    m : float
        Mass flow rate [kg/s]
    x : float
        Quality at the specific tube interval []
    D : float
        Diameter of the tube [m]
    rhol : float
        Density of the liquid [kg/m^3]
    rhog : float
        Density of the gas [kg/m^3]
    mul : float
        Viscosity of liquid [Pa*s]
    kl : float
        Thermal conductivity of liquid [W/m/K]
    Hvap : float
        Heat of vaporization of liquid [J/kg]
    sigma : float
        Surface tension of liquid [N/m]
    q : float, optional
        Heat flux to wall [W/m^2]
    Te : float, optional
        Excess temperature of wall, [K]

    Returns
    -------
    h : float
        Heat transfer coefficient [W/m^2/K]

    Notes
    -----
    [1]_ has been reviewed. The code to derive the form with `Te` specified is
    as follows:
    
    >>> from sympy import *
    >>> h, A, Te, G, Hvap = symbols('h, A, Te, G, Hvap', positive=True, real=True)
    >>> solve(Eq(h, A*(h*Te/G/Hvap)**0.3), h)
    [A**(10/7)*Te**(3/7)/(G**(3/7)*Hvap**(3/7))]
    
    [1]_ used 18 sets of experimental data to derive the results, covering 
    hydraulic diameters from 0.19 to 3.1 mm and 12 different fluids.

    Examples
    --------
    >>> Li_Wu(m=1, x=0.2, D=0.3, rhol=567., rhog=18.09, kl=0.086, mul=156E-6, sigma=0.02, Hvap=9E5, q=1E5)
    5345.409399239493

    References
    ----------
    .. [1] Li, Wei, and Zan Wu. "A General Correlation for Evaporative Heat 
       Transfer in Micro/mini-Channels." International Journal of Heat and Mass
       Transfer 53, no. 9-10 (April 2010): 1778-87. 
       doi:10.1016/j.ijheatmasstransfer.2010.01.012.
    .. [2] Fang, Xiande, Zhanru Zhou, and Dingkun Li. "Review of Correlations 
       of Flow Boiling Heat Transfer Coefficients for Carbon Dioxide."
       International Journal of Refrigeration 36, no. 8 (December 2013): 
       2017-39. doi:10.1016/j.ijrefrig.2013.05.015.
    .. [3] Kim, Sung-Min, and Issam Mudawar. "Review of Databases and 
       Predictive Methods for Pressure Drop in Adiabatic, Condensing and 
       Boiling Mini/micro-Channel Flows." International Journal of Heat and 
       Mass Transfer 77 (October 2014): 74-97. 
       doi:10.1016/j.ijheatmasstransfer.2014.04.035.
    '''
    G = m/(pi/4*D**2)
    Rel = G*D*(1-x)/mul
    Bo = Bond(rhol=rhol, rhog=rhog, sigma=sigma, L=D)
    if q:
        Bg = Boiling(G=G, q=q, Hvap=Hvap)
        htp = 334*Bg**0.3*(Bo*Rel**0.36)**0.4*kl/D
    elif Te:
        A = 334*(Bo*Rel**0.36)**0.4*kl/D
        htp = A**(10/7.)*Te**(3/7.)/(G**(3/7.)*Hvap**(3/7.))
    else:
        raise Exception('Either q or Te is needed for this correlation')
    return htp



def Sun_Mishima(m, D, rhol, rhog, mul, kl, Hvap, sigma, q=None, Te=None):
    r'''Calculates heat transfer coefficient for film boiling of saturated
    fluid in any orientation of flow. Correlation
    is as shown in [1]_, and also reviewed in [2]_ and [3]_.
    
    Either the heat flux or excess temperature is required for the calculation
    of heat transfer coefficient. Uses liquid-only Reynolds number, Weber
    number, and Boiling numer. Weber number is defined in terms of the velocity
    if all fluid were liquid.

    .. math::
        h_{tp} = \frac{ 6 Re_{lo}^{1.05} Bg^{0.54}}
        {We_l^{0.191}(\rho_l/\rho_g)^{0.142}}\frac{k_l}{D}
        
        Re_{lo} = \frac{G_{tp}D}{\mu_l}
    
    Parameters
    ----------
    m : float
        Mass flow rate [kg/s]
    D : float
        Diameter of the tube [m]
    rhol : float
        Density of the liquid [kg/m^3]
    rhog : float
        Density of the gas [kg/m^3]
    mul : float
        Viscosity of liquid [Pa*s]
    kl : float
        Thermal conductivity of liquid [W/m/K]
    Hvap : float
        Heat of vaporization of liquid [J/kg]
    sigma : float
        Surface tension of liquid [N/m]
    q : float, optional
        Heat flux to wall [W/m^2]
    Te : float, optional
        Excess temperature of wall, [K]

    Returns
    -------
    h : float
        Heat transfer coefficient [W/m^2/K]

    Notes
    -----
    [1]_ has been reviewed. The code to derive the form with `Te` specified is
    as follows:
    
    >>> from sympy import *
    >>> h, A, Te, G, Hvap = symbols('h, A, Te, G, Hvap', positive=True, real=True)
    >>> solve(Eq(h, A*(h*Te/G/Hvap)**0.54), h)
    [A**(50/23)*Te**(27/23)/(G**(27/23)*Hvap**(27/23))]
    
    [1]_ used 2501 data points to derive the results, covering 
    hydraulic diameters from 0.21 to 6.05 mm and 11 different fluids.
    

    Examples
    --------
    >>> Sun_Mishima(m=1, D=0.3, rhol=567., rhog=18.09, kl=0.086, mul=156E-6, sigma=0.02, Hvap=9E5, Te=10)
    507.6709168372167

    References
    ----------
    .. [1] Sun, Licheng, and Kaichiro Mishima. "An Evaluation of Prediction 
       Methods for Saturated Flow Boiling Heat Transfer in Mini-Channels." 
       International Journal of Heat and Mass Transfer 52, no. 23-24 (November 
       2009): 5323-29. doi:10.1016/j.ijheatmasstransfer.2009.06.041.
    .. [2] Fang, Xiande, Zhanru Zhou, and Dingkun Li. "Review of Correlations 
       of Flow Boiling Heat Transfer Coefficients for Carbon Dioxide."
       International Journal of Refrigeration 36, no. 8 (December 2013): 
       2017-39. doi:10.1016/j.ijrefrig.2013.05.015.
    '''
    G = m/(pi/4*D**2)
    V = G/rhol
    Relo = G*D/mul
    We = Weber(V=V, L=D, rho=rhol, sigma=sigma)
    if q:
        Bg = Boiling(G=G, q=q, Hvap=Hvap)
        htp = 6*Relo**1.05*Bg**0.54/(We**0.191*(rhol/rhog)**0.142)*kl/D
    elif Te:
        A = 6*Relo**1.05/(We**0.191*(rhol/rhog)**0.142)*kl/D
        htp = A**(50/23.)*Te**(27/23.)/(G**(27/23.)*Hvap**(27/23.))
    else:
        raise Exception('Either q or Te is needed for this correlation')
    return htp


def Thome(m, x, D, rhol, rhog, mul, mug, kl, kg, Cpl, Cpg, Hvap, sigma, Psat, 
          Pc, q=None, Te=None):
    r'''Calculates heat transfer coefficient for film boiling of saturated
    fluid in any orientation of flow. Correlation
    is as developed in [1]_ and [2]_, and also reviewed [3]_. This is a 
    complicated model, but expected to have more accuracy as a result.
    
    Either the heat flux or excess temperature is required for the calculation
    of heat transfer coefficient. The solution for a specified excess 
    temperature is solved numerically, making it slow.
    
    .. math::
        h(z) = \frac{t_l}{\tau} h_l(z) +\frac{t_{film}}{\tau} h_{film}(z) 
        +  \frac{t_{dry}}{\tau} h_{g}(z) 
    
        h_{l/g}(z) = (Nu_{lam}^4 + Nu_{trans}^4)^{1/4} k/D
        
        Nu_{laminar} = 0.91 {Pr}^{1/3} \sqrt{ReD/L(z)}
        
        Nu_{trans} = \frac{ (f/8) (Re-1000)Pr}{1+12.7 (f/8)^{1/2} (Pr^{2/3}-1)}
        \left[ 1 + \left( \frac{D}{L(z)}\right)^{2/3}\right]
        
        f = (1.82 \log_{10} Re - 1.64 )^{-2}
        
        L_l = \frac{\tau G_{tp}}{\rho_l}(1-x)
        
        L_{dry} = v_p t_{dry}
        
        t_l = \frac{\tau}{1 + \frac{\rho_l}{\rho_g}\frac{x}{1-x}}
        
        t_v = \frac{\tau}{1 + \frac{\rho_g}{\rho_l}\frac{1-x}{x}}
        
        \tau = \frac{1}{f_{opt}}
        
        f_{opt} = \left(\frac{q}{q_{ref}}\right)^{n_f}
        
        q_{ref} = 3328\left(\frac{P_{sat}}{P_c}\right)^{-0.5}
        
        t_{dry,film} = \frac{\rho_l \Delta H_{vap}}{q}[\delta_0(z) - 
        \delta_{min}]
        
        \frac{\delta_0}{D} = C_{\delta 0}\left(3\sqrt{\frac{\nu_l}{v_p D}}
        \right)^{0.84}\left[(0.07Bo^{0.41})^{-8} + 0.1^{-8}\right]^{-1/8}
        
        Bo = \frac{\rho_l D}{\sigma} v_p^2
        
        v_p = G_{tp} \left[\frac{x}{\rho_g} + \frac{1-x}{\rho_l}\right]
        
        h_{film}(z) = \frac{2 k_l}{\delta_0(z) + \delta_{min}(z)}
        
        \delta_{min} = 0.3\cdot 10^{-6} \text{m}
        
        C_{\delta,0} = 0.29
        
        n_f = 1.74
        
    if t dry film > tv:
    
    .. math::
        \delta_{end}(x) = \delta(z, t_v)
        
        t_{film} = t_v
        
        t_{dry} = 0
    
    Otherwise:
    
    .. math::
        \delta_{end}(z) = \delta_{min}
        
        t_{film} = t_{dry,film}
        
        t_{dry} = t_v - t_{film}
    
    Parameters
    ----------
    m : float
        Mass flow rate [kg/s]
    x : float
        Quality at the specific tube interval []
    D : float
        Diameter of the tube [m]
    rhol : float
        Density of the liquid [kg/m^3]
    rhog : float
        Density of the gas [kg/m^3]
    mul : float
        Viscosity of liquid [Pa*s]
    mug : float
        Viscosity of gas [Pa*s]
    kl : float
        Thermal conductivity of liquid [W/m/K]
    kg : float
        Thermal conductivity of gas [W/m/K]
    Cpl : float
        Heat capacity of liquid [J/kg/K]
    Cpg : float
        Heat capacity of gas [J/kg/K]
    Hvap : float
        Heat of vaporization of liquid [J/kg]
    sigma : float
        Surface tension of liquid [N/m]
    Psat : float
        Vapor pressure of fluid, [Pa]
    Pc : float
        Critical pressure of fluid, [Pa]
    q : float, optional
        Heat flux to wall [W/m^2]
    Te : float, optional
        Excess temperature of wall, [K]

    Returns
    -------
    h : float
        Heat transfer coefficient [W/m^2/K]

    Notes
    -----
    [1]_ and [2]_ have been reviewed, and are accurately reproduced in [3]_.
    
    [1]_ used data from 7 studies, covering 7 fluids and Dh from 0.7-3.1 mm, 
    heat flux from 0.5-17.8 W/cm^2, x from 0.01-0.99, and G from 50-564 
    kg/m^2/s.
    
    Liquid and/or gas slugs are both considered, and are hydrodynamically
    developing. `Ll` is the calculated length of liquid slugs, and `L_dry` 
    is the same for vapor slugs.
    
    Because of the complexity of the model and that there is some logic in this
    function, `Te` as an input may lead to a different solution that the
    calculated `q` will in return.
    
    Examples
    --------
    >>> Thome(m=1, x=0.4, D=0.3, rhol=567., rhog=18.09, kl=0.086, kg=0.2,
    ... mul=156E-6, mug=1E-5, Cpl=2300, Cpg=1400, sigma=0.02, Hvap=9E5, 
    ... Psat=1E5, Pc=22E6, q=1E5)
    1633.008836502032

    References
    ----------
    .. [1] Thome, J. R., V. Dupont, and A. M. Jacobi. "Heat Transfer Model for 
       Evaporation in Microchannels. Part I: Presentation of the Model." 
       International Journal of Heat and Mass Transfer 47, no. 14-16 (July 
       2004): 3375-85. doi:10.1016/j.ijheatmasstransfer.2004.01.006.
    .. [2] Dupont, V., J. R. Thome, and A. M. Jacobi. "Heat Transfer Model for 
       Evaporation in Microchannels. Part II: Comparison with the Database." 
       International Journal of Heat and Mass Transfer 47, no. 14-16 (July 
       2004): 3387-3401. doi:10.1016/j.ijheatmasstransfer.2004.01.007.
    .. [3] Bertsch, Stefan S., Eckhard A. Groll, and Suresh V. Garimella. 
       "Review and Comparative Analysis of Studies on Saturated Flow Boiling in
       Small Channels." Nanoscale and Microscale Thermophysical Engineering 12,
       no. 3 (September 4, 2008): 187-227. doi:10.1080/15567260802317357.
    '''
    if q is None and Te:
        to_solve = lambda q : q/Thome(m=m, x=x, D=D, rhol=rhol, rhog=rhog, kl=kl, kg=kg, mul=mul, mug=mug, Cpl=Cpl, Cpg=Cpg, sigma=sigma, Hvap=Hvap, Psat=Psat, Pc=Pc, q=q) - Te
#        q = newton(to_solve, 1E4)
        q = fsolve(to_solve, 1E4)
        return Thome(m=m, x=x, D=D, rhol=rhol, rhog=rhog, kl=kl, kg=kg, mul=mul, mug=mug, Cpl=Cpl, Cpg=Cpg, sigma=sigma, Hvap=Hvap, Psat=Psat, Pc=Pc, q=q)
    elif q is None and Te is None:
        raise Exception('Either q or Te is needed for this correlation')
    C_delta0 = 0.3E-6
    G = m/(pi/4*D**2)
    Rel = G*D*(1-x)/mul
    Reg = G*D*x/mug
    qref = 3328*(Psat/Pc)**-0.5
    fopt = (q/qref)**1.74
    tau = 1./fopt
    
    vp = G*(x/rhog + (1-x)/rhol)
    Bo = rhol*D/sigma*vp**2 # Not standard definition
    nul = nu_mu_converter(rho=rhol, mu=mul)
    delta0 = D*0.29*(3*(nul/vp/D)**0.5)**0.84*((0.07*Bo**0.41)**-8 + 0.1**-8)**(-1/8.)
    
    tl = tau/(1 + rhol/rhog*(x/(1.-x)))
    tv = tau/(1 ++ rhog/rhol*((1.-x)/x))

    t_dry_film = rhol*Hvap/q*(delta0 - C_delta0)
    if t_dry_film > tv:
        t_film = tv
        delta_end = delta0 - q/rhol/Hvap*tv # what could time possibly be?
        t_dry = 0
    else:
        t_film = t_dry_film
        delta_end = C_delta0
        t_dry = tv-t_film
    Ll = tau*G/rhol*(1-x)
    Ldry = t_dry*vp


    Prg = Prandtl(Cp=Cpg, k=kg, mu=mug)
    Prl = Prandtl(Cp=Cpl, k=kl, mu=mul)
    fg = (1.82*log10(Reg) - 1.64)**-2
    fl = (1.82*log10(Rel) - 1.64)**-2
    
    Nu_lam_Zl = 2*0.455*(Prl)**(1/3.)*(D*Rel/Ll)**0.5
    Nu_trans_Zl = turbulent_Gnielinski(Re=Rel, Pr=Prl, fd=fl)*(1 + (D/Ll)**(2/3.))
    if Ldry == 0:
        Nu_lam_Zg, Nu_trans_Zg = 0, 0
    else:
        Nu_lam_Zg = 2*0.455*(Prg)**(1/3.)*(D*Reg/Ldry)**0.5
        Nu_trans_Zg = turbulent_Gnielinski(Re=Reg, Pr=Prg, fd=fg)*(1 + (D/Ldry)**(2/3.))
        
    h_Zg = kg/D*(Nu_lam_Zg**4 + Nu_trans_Zg**4)**0.25
    h_Zl = kl/D*(Nu_lam_Zl**4 + Nu_trans_Zl**4)**0.25
        
    h_film = 2*kl/(delta0 + C_delta0)
    h = tl/tau*h_Zl + t_film/tau*h_film + t_dry/tau*h_Zg
    return h
        

def Yun_Heo_Kim(m, x, D, rhol, mul, Hvap, sigma, q=None, Te=None):
    r'''Calculates heat transfer coefficient for film boiling of saturated
    fluid in any orientation of flow. Correlation
    is as shown in [1]_ and [2]_, and also reviewed in [3]_.
    
    Either the heat flux or excess temperature is required for the calculation
    of heat transfer coefficient. Uses liquid Reynolds number, Weber
    number, and Boiling numer. Weber number is defined in terms of the velocity
    if all fluid were liquid.

    .. math::
        h_{tp} = 136876(Bg\cdot We_l)^{0.1993} Re_l^{-0.1626}
        
        Re_l = \frac{G D (1-x)}{\mu_l}
        
        We_l = \frac{G^2 D}{\rho_l \sigma}
    
    Parameters
    ----------
    m : float
        Mass flow rate [kg/s]
    x : float
        Quality at the specific tube interval []
    D : float
        Diameter of the tube [m]
    rhol : float
        Density of the liquid [kg/m^3]
    mul : float
        Viscosity of liquid [Pa*s]
    Hvap : float
        Heat of vaporization of liquid [J/kg]
    sigma : float
        Surface tension of liquid [N/m]
    q : float, optional
        Heat flux to wall [W/m^2]
    Te : float, optional
        Excess temperature of wall, [K]

    Returns
    -------
    h : float
        Heat transfer coefficient [W/m^2/K]

    Notes
    -----
    [1]_ has been reviewed. The code to derive the form with `Te` specified is
    as follows:
    
    >>> from sympy import *
    >>> h, A = symbols('h, A', positive=True, real=True)
    >>> solve(Eq(h, A*(h)**0.1993), h)
    [A**(10000/8707)]        

    Examples
    --------
    >>> Yun_Heo_Kim(m=1, x=0.4, D=0.3, rhol=567., mul=156E-6, sigma=0.02, Hvap=9E5, q=1E4)
    9479.313988550184

    References
    ----------
    .. [1] Yun, Rin, Jae Hyeok Heo, and Yongchan Kim. "Evaporative Heat 
       Transfer and Pressure Drop of R410A in Microchannels." International 
       Journal of Refrigeration 29, no. 1 (January 2006): 92-100. 
       doi:10.1016/j.ijrefrig.2005.08.005. 
    .. [2] Yun, Rin, Jae Hyeok Heo, and Yongchan Kim. "Erratum to 'Evaporative 
       Heat Transfer and Pressure Drop of R410A in Microchannels; [Int. J. 
       Refrigeration 29 (2006) 92-100]." International Journal of Refrigeration
       30, no. 8 (December 2007): 1468. doi:10.1016/j.ijrefrig.2007.08.003.
    .. [3] Bertsch, Stefan S., Eckhard A. Groll, and Suresh V. Garimella. 
       "Review and Comparative Analysis of Studies on Saturated Flow Boiling in
       Small Channels." Nanoscale and Microscale Thermophysical Engineering 12,
       no. 3 (September 4, 2008): 187-227. doi:10.1080/15567260802317357.
    '''
    G = m/(pi/4*D**2)
    V = G/rhol
    Rel = G*D*(1-x)/mul
    We = Weber(V=V, L=D, rho=rhol, sigma=sigma)
    if q:
        Bg = Boiling(G=G, q=q, Hvap=Hvap)
        htp = 136876*(Bg*We)**0.1993*Rel**-0.1626
    elif Te:
        A = 136876*(We)**0.1993*Rel**-0.1626*(Te/G/Hvap)**0.1993
        htp = A**(10000/8007.)
    else:
        raise Exception('Either q or Te is needed for this correlation')
    return htp

#q = 1E4
#h1 = Yun_Heo_Kim(m=1, x=0.4, D=0.3, rhol=567., mul=156E-6, sigma=0.02, Hvap=9E5, q=q)
#Te = q/h1
#print('h1', h1, 'Te', Te)
#print([Yun_Heo_Kim(m=1, x=0.4, D=0.3, rhol=567., mul=156E-6, sigma=0.02, Hvap=9E5, Te=Te)])
#    
###q = 1E5
##h = Thome(m=10, x=0.5, D=0.3, rhol=567., rhog=18.09, kl=0.086, kg=0.2, mul=156E-6, mug=1E-5, Cpl=2300, Cpg=1400, sigma=0.02, Hvap=9E5, Psat=1E5, Pc=22E6, q=q)
##print(h)
#Te = q/h
#print(Te)
#print(Thome(m=10, x=0.5, D=0.3, rhol=567., rhog=18.09, kl=0.086, kg=0.2, mul=156E-6, mug=1E-5, Cpl=2300, Cpg=1400, sigma=0.02, Hvap=9E5, Psat=1E5, Pc=22E6, Te=Te))
##print('Te', Te)
#to_sovlve = lambda Te : Thome(m=10, x=0.5, D=0.3, rhol=567., rhog=18.09, kl=0.086, kg=0.2, mul=156E-6, mug=1E-5, Cpl=2300, Cpg=1400, sigma=0.02, Hvap=9E5, Psat=1E5, Pc=22E6, q=q) - Te
#print(fsolve(to_sovlve, 2E5))
import sys
import cmath
from math import pi, sqrt
import numpy as np
import sympy as sp
from sympy.matrices import Matrix, zeros
import mpi4py.MPI as mpi
import time

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cm

import pyLBM
from pyLBM.Elements import *
import pyLBM.Geometry as pyLBMGeom
import pyLBM.Simulation as pyLBMSimu
import pyLBM.Domain as pyLBMDom

X, Y, Z, LA = sp.symbols('X,Y,Z,LA')
u = [[sp.Symbol("m[%d][%d]"%(i,j)) for j in xrange(25)] for i in xrange(10)]

def init_rho(x,y,val):
    return val*np.ones((x.shape[0], y.shape[0]), dtype='float64')

def init_qx(x,y,val):
    return val*np.ones((x.shape[0], y.shape[0]), dtype='float64')

def init_qy(x,y,val):
    return val*np.ones((x.shape[0], y.shape[0]), dtype='float64')

def init_un(x,y):
    n = x.shape[0]
    m = y.shape[0]
    uu = np.zeros((n, m), dtype='float64')
    uu[n/2,m/2] = 1.
    return uu

def bounce_back(sol):
    ns = sol.Scheme.nscheme
    for n in xrange(ns):
        for k in xrange(sol.Scheme.Stencil.nv[n]):
            ksym = sol.Scheme.Stencil.numV_sym[n][k]
            vk_dom = sol.Scheme.Stencil.numv[n][k]
            vkx, vky = (int)(sol.Scheme.Stencil.V[n][0,k]), (int)(sol.Scheme.Stencil.V[n][1,k])
            ind_vk_y, ind_vk_x = np.where(sol.Domain.distance[vk_dom,:,:]<sol.Domain.valin)
            sol.F[n][ksym, ind_vk_x+vkx, ind_vk_y+vky] = sol.F[n][k, ind_vk_x, ind_vk_y]
    
def periodique(sol):
    ns = sol.Scheme.nscheme
    xb = sol.Domain.indbe[0][0]
    xe = sol.Domain.indbe[0][1]
    yb = sol.Domain.indbe[1][0]
    ye = sol.Domain.indbe[1][1]
    for n in xrange(ns):
        sol.F[n][:, 0:xb,  yb:ye] = sol.F[n][:, xe-xb:xe, yb:ye   ] # E -> W
        sol.F[n][:, xe:,   yb:ye] = sol.F[n][:, xb:xb+xb, yb:ye   ] # W -> E
        sol.F[n][:, xb:xe, 0:yb ] = sol.F[n][:, xb:xe,    ye-yb:ye] # N -> S
        sol.F[n][:, xb:xe, ye:  ] = sol.F[n][:, xb:xe,    yb:yb+yb] # S -> N
        sol.F[n][:, 0:xb,  0:yb ] = sol.F[n][:, xe-xb:xe, ye-yb:ye] # NE -> SW
        sol.F[n][:, 0:xb,  ye:  ] = sol.F[n][:, xe-xb:xe, yb:yb+yb] # SE -> NW
        sol.F[n][:, xe:,   0:yb ] = sol.F[n][:, xb:xb+xb, ye-yb:ye] # NW -> SE
        sol.F[n][:, xe:,   ye:  ] = sol.F[n][:, xb:xb+xb, yb:yb+yb] # SW -> NE


def plot_F(sol):
    Sten = sol.Scheme.Stencil
    vxm  = Sten.vmax[0]
    vym  = Sten.vmax[1]
    nx   = 1+2*vxm
    ny   = 1+2*vym
    for k in xrange(Sten.nv[0]):
        vx = (int)(Sten.V[0][0,k])
        vy = (int)(Sten.V[0][1,k])
        numim = nx*(vym-vy) + vx+vxm + 1
        plt.subplot(nx*100+ny*10+numim)
        plt.imshow(np.float32((sol.F[0][k,1:-1,1:-1])).transpose(), origin='lower', cmap=cm.jet, interpolation='nearest')
        plt.title('({1:d},{2:d}) at t = {0:f}'.format(sol.t, vx, vy))
    plt.draw()
    plt.pause(1.e0)

def plot_m(sol,valeq):
    for i in xrange(3):
        for j in xrange(3):
            k = 3*i+j
            plt.subplot(331+k)
            plt.plot(sol.t,sol.m[0][k,3,3],'k*',[sol.t,sol.t+sol.dt],[valeq[k],valeq[k]],'r')
            plt.title('m[{1:d}] at t = {0:f}'.format(sol.t, k))    

def test_transport():
    # parameters
    dim = 2 # spatial dimension
    xmin, xmax, ymin, ymax = -0.5, 4.5, -0.5, 4.5
    dx = 1. # spatial step
    la = 1. # velocity of the scheme
    Tf = 5

    dico_geometry = {'dim':dim,
                     'box':{'x':[xmin, xmax], 'y':[ymin, ymax], 'label':0},
                     'Elements':[]
                     }
    #"""
    rhoo = 1.
    mu   = 1.e-2 #0.00185
    zeta = 1.e-2
    dummy = 3.0/(la*rhoo*dx)
    s3 = 1.0/(0.5+zeta*dummy)
    s4 = s3
    s5 = s4
    s6 = s4
    s7 = 1.0/(0.5+mu*dummy)
    s8 = s7
    s  = [0.,0.,0.,s3,s4,s5,s6,s7,s8]
    dummy = 1./(LA**2*rhoo)
    qx2 = dummy*u[0][1]**2
    qy2 = dummy*u[0][2]**2
    q2  = qx2+qy2
    qxy = dummy*u[0][1]*u[0][2]

    dico   = {'dim':dim,
              'Geometry':dico_geometry,
              'space_step':dx,
              'scheme_velocity':la,
              'number_of_schemes':1,
              'init':'densities',
              0:{'velocities':range(9),
                 'polynomials':Matrix([1,
                                       LA*X, LA*Y,
                                       3*(X**2+Y**2)-4,
                                       0.5*(9*(X**2+Y**2)**2-21*(X**2+Y**2)+8),
                                       3*X*(X**2+Y**2)-5*X, 3*Y*(X**2+Y**2)-5*Y,
                                       X**2-Y**2, X*Y]),
                 'relaxation_parameters':s,
                 'equilibrium':Matrix([u[0][0],
                                       u[0][1], u[0][2],
                                       -2*u[0][0] + 3*q2,
                                       u[0][0]+1.5*q2,
                                       u[0][1]/LA, u[0][2]/LA,
                                       qx2-qy2, qxy]),
                 'init':{0:init_un,
                         1:init_un,
                         2:init_un,
                         3:init_un,
                         4:init_un,
                         5:init_un,
                         6:init_un,
                         7:init_un,
                         8:init_un}
                 }
            }
    """
    s = [0., 1.5, 1.5, 1.5, 1.5]
    dico   = {'dim':dim,
              'Geometry':dico_geometry,
              'space_step':dx,
              'scheme_velocity':la,
              'number_of_schemes':1,
              'init':'densities',
              0:{'velocities':[0,5,6,7,8],
                 'polynomials':Matrix([1, LA*X, LA*Y, X**2+Y**2, X*Y]),
                 'relaxation_parameters':s,
                 'equilibrium':Matrix([u[0][0], 0., 0., 0.5*u[0][0], 0.]),
                 'init':{0:init_un, 1:init_un, 2:init_un, 3:init_un, 4:init_un}
                 }
            }
    """
    geom = pyLBMGeom.Geometry(dico)
    dom = pyLBMDom.Domain(geom,dico)
    #pyLBMDom.visualize(dom,opt=1)
    sol = pyLBMSimu.Simulation(dico, geom)
    print sol.Scheme.Code_Transport
    fig = plt.figure(0,figsize=(16, 8))
    fig.clf()
    plt.ion()
    plot_F(sol)
    while (sol.t<Tf-0.5*sol.dt):
        sol.Scheme.m2f(sol.m, sol.F)
        periodique(sol)
        #bounce_back(sol)
        sol.Scheme.transport(sol.F)
        sol.Scheme.f2m(sol.F, sol.m)
        sol.t += sol.dt
        plot_F(sol)        
    plt.ioff()
    plt.show()

def test_relaxation():
    # parameters
    dim = 2 # spatial dimension
    xmin, xmax, ymin, ymax = -1.5, 1.5, -1.5, 1.5
    dx = 1. # spatial step
    la = 1. # velocity of the scheme
    Tf = 50
    rhoo = 1.
    s  = [0., 0., 0., 1.9, 1.8, 1.7, 1.75, 1.85, 1.95]

    rhoi = 1.
    qxi = -0.2
    qyi = 1.2
    
    dummy = 1./(LA**2*rhoo)
    qx2 = dummy*u[0][1]**2
    qy2 = dummy*u[0][2]**2
    q2  = qx2+qy2
    qxy = dummy*u[0][1]*u[0][2]
    dico_geometry = {'dim':dim,
                     'box':{'x':[xmin, xmax], 'y':[ymin, ymax], 'label':0},
                     'Elements':[]
                     }
    dico   = {'dim':dim,
              'Geometry':dico_geometry,
              'space_step':dx,
              'scheme_velocity':la,
              'number_of_schemes':1,
              'init':'moments',
              0:{'velocities':range(9),
                 'polynomials':Matrix([1,
                                       LA*X, LA*Y,
                                       3*(X**2+Y**2)-4,
                                       0.5*(9*(X**2+Y**2)**2-21*(X**2+Y**2)+8),
                                       3*X*(X**2+Y**2)-5*X, 3*Y*(X**2+Y**2)-5*Y,
                                       X**2-Y**2, X*Y]),
                 'relaxation_parameters':s,
                 'equilibrium':Matrix([u[0][0],
                                       u[0][1], u[0][2],
                                       -2*u[0][0] + 3*q2,
                                       u[0][0]+1.5*q2,
                                       u[0][1]/LA, u[0][2]/LA,
                                       qx2-qy2, qxy]),
                 'init':{0:init_rho, 1:init_qx, 2:init_qy},
                 'init_args':{0:(rhoi,), 1:(qxi,), 2:(qyi,)}
                 }
            }
    
    geom = pyLBMGeom.Geometry(dico)
    dom = pyLBMDom.Domain(geom,dico)
    sol = pyLBMSimu.Simulation(dico, geom)
    print sol.Scheme.Code_Relaxation
    q2 = qxi**2+qyi**2
    valeq = [rhoi, qxi, qyi, -2*rhoi+3*q2, rhoi+1.5*q2, qxi, qyi, qxi**2-qyi**2, qxi*qyi]
    sol.m[0][3:,:,:] = 0.
    fig = plt.figure(0,figsize=(16, 8))
    fig.clf()
    plt.ion()
    plot_m(sol,valeq)
    while (sol.t<Tf-0.5*sol.dt):
        sol.Scheme.m2f(sol.m, sol.F)
        sol.Scheme.f2m(sol.F, sol.m)
        sol.Scheme.relaxation(sol.m)
        sol.t += sol.dt
        plot_m(sol,valeq)        
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    test_transport()
    test_relaxation()

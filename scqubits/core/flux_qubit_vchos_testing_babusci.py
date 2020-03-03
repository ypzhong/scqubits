import numpy as np
import scipy as sp
import itertools
import scipy.constants as const
from scipy.special import hermite
from scipy.special import factorial
from scipy.special import comb
import scipy.integrate as integrate
import math

import scqubits.core.constants as constants
import scqubits.utils.plotting as plot
from scqubits.core.discretization import GridSpec, Grid1d
from scqubits.core.qubit_base import QubitBaseClass
from scqubits.utils.spectrum_utils import standardize_phases, order_eigensystem


#-Flux Qubit using VCHOS 

def heat(x, y, n):
    heatsum = 0.0
    for k in range(math.floor(float(n)/2.0)+1):
        heatsum += x**(n-2*k)*y**(k)/(factorial(n-2*k)*factorial(k))
    return(heatsum*factorial(n))

def Hmn(m, n, x, y, w, z, tau):
    Hmnsum = 0.0
    for i in range(min(m,n)+1):
        Hmnsum += (factorial(m)*factorial(n)/(factorial(m-i)*factorial(n-i)*factorial(i))
                   *heat(x,y,m-i)*heat(w,z,n-i)*tau**i)
    return(Hmnsum)

def Imn(m,n,y,z,a,b,c,d,f,alpha):
    xbar = b+(a*alpha/(2.0*f))
    ybar = y+(a**2)/(4.0*f)
    wbar = d+(c*alpha)/(2.0*f)
    zbar = z+(c**2)/(4.0*f)
    tau  = a*c/(2.0*f)
    return(np.sqrt(np.pi/f)*np.exp(alpha**2/(4.0*f))*Hmn(m,n,xbar,ybar,wbar,zbar,tau)/
           (np.sqrt(np.sqrt(np.pi)*2**n*factorial(n))*np.sqrt(np.sqrt(np.pi)*2**m*factorial(m))))

def Rmnk(m,n,y,z,a,b,c,d,f,alpha,k):
    xbar = b+(a*alpha/(2.0*f))
    ybar = y+(a**2)/(4.0*f)
    wbar = d+(c*alpha)/(2.0*f)
    zbar = z+(c**2)/(4.0*f)
    tau  = a*c/(2.0*f)
    Rmnksum = 0.0
    for l in range(k+1):
        if(m-l>=0 and n-k+l>=0):
            Rmnksum+=(comb(k,l)*((a/c)**l)*factorial(m)*factorial(n)/
                      (factorial(m-l)*factorial(n-k+l)))*Hmn(m-l,n-k+l,xbar,ybar,wbar,zbar,tau)
    return(Rmnksum*(c/(2.0*f))**k)

def pImn(p,m,n,y,z,a,b,c,d,f,alpha):
    pImnsum=0.0
    if (m<0 or n<0):
        return (0.0)                                       
    for k in range(p+1):
        pImnsum+=comb(p,k)*heat(alpha/(2.0*f),1.0/(4.0*f),p-k)*Rmnk(m,n,y,z,a,b,c,d,f,alpha,k)
    return(np.sqrt(np.pi/f)*np.exp(alpha**2/(4.0*f))*pImnsum/
           (np.sqrt(np.sqrt(np.pi)*(2**n)*factorial(n))
            *np.sqrt(np.sqrt(np.pi)*(2**m)*factorial(m))))

#Class for testing FQV using Babusci integrals

class FluxQubitVCHOSTestingBabusci(QubitBaseClass):
    def __init__(self, ECJ, ECg, EJ, ng1, ng2, alpha, flux, kmax, num_exc):
        self.ECJ = ECJ
        self.EJ = EJ
        self.ECg = ECg
        self.ng1 = ng1
        self.ng2 = ng2
        self.alpha = alpha
        self.flux = flux
        self.kmax = kmax
        self.num_exc = num_exc
        self.hGHz = const.h * 10**9
        self.e = np.sqrt(4.0*np.pi*const.alpha)
        self.Z0 = 1. / (2*self.e)**2
        self.Phi0 = 1. / (2*self.e)
        
        self._evec_dtype = np.float_
        self._default_grid = Grid1d(-6.5*np.pi, 6.5*np.pi, 651)
        
        def potential(self, phiarray):
        """
        Flux qubit potential evaluated at `phi1` and `phi2` 
        """
        phi1 = phiarray[0]
        phi2 = phiarray[1]
        return (-self.EJ*np.cos(phi1) -self.EJ*np.cos(phi2)
                -self.EJ*self.alpha*np.cos(phi1-phi2+2.0*np.pi*self.flux))
    
    def build_capacitance_matrix(self):
        """Return the capacitance matrix"""
        Cmat = np.zeros((2, 2))
                
        CJ = self.e**2 / (2.*self.ECJ)
        Cg = self.e**2 / (2.*self.ECg)
        
        Cmat[0, 0] = CJ + self.alpha*CJ + Cg
        Cmat[1, 1] = CJ + self.alpha*CJ + Cg
        Cmat[0, 1] = -self.alpha*CJ
        Cmat[1, 0] = -self.alpha*CJ
        
        return Cmat
    
    def build_EC_matrix(self):
        """Return the charging energy matrix"""
        Cmat = self.build_capacitance_matrix()
        return  0.5 * self.e**2 * sp.linalg.inv(Cmat)
    
    def build_gamma_matrix(self):
        """
        Return linearized potential matrix
        
        Note that we must divide by Phi_0^2 since Ej/Phi_0^2 = 1/Lj,
        or one over the effective impedance of the junction.
        
        """
        gmat = np.zeros((2,2))
        
        global_min = self.sorted_minima()[0]
        phi1_min = global_min[0]
        phi2_min = global_min[1]
        
        gamma = self.EJ / self.Phi0**2
        
        gmat[0, 0] = gamma*np.cos(phi1_min) + self.alpha*gamma*np.cos(2*np.pi*self.flux 
                                                                      + phi1_min - phi2_min)
        gmat[1, 1] = gamma*np.cos(phi2_min) + self.alpha*gamma*np.cos(2*np.pi*self.flux 
                                                                      + phi1_min - phi2_min)
        gmat[0, 1] = gmat[1, 0] = -self.alpha*gamma*np.cos(2*np.pi*self.flux + phi1_min - phi2_min)
        
        return gmat
        
    def Xi_matrix(self):
        """Construct the Xi matrix, encoding the oscillator lengths of each dimension"""
        Cmat = self.build_capacitance_matrix()
        gmat = self.build_gamma_matrix()
        
        omegasq, eigvec = sp.linalg.eigh(gmat, b=Cmat)
        
        Ximat = np.array([eigvec[:,i]*np.sqrt(np.sqrt(1./omegasq[i]))
                          * np.sqrt(1./self.Z0) for i in range(Cmat.shape[0])])
        
        # Note that the actual Xi matrix is the transpose of above, 
        # due to list comprehension syntax reasons. Here we are 
        # asserting that \Xi^T C \Xi = \Omega^{-1}/Z0
        assert(np.allclose(np.matmul(Ximat, np.matmul(Cmat, np.transpose(Ximat))),
                              sp.linalg.inv(np.diag(np.sqrt(omegasq)))/self.Z0))

        return np.transpose(Ximat)
    
    def _check_if_new_minima(self, new_minima, minima_holder):
        """
        Helper function for find_minima, checking if minima is
        already represented in minima_holder. If so, 
        _check_if_new_minima returns False.
        """
        new_minima_bool = True
        for minima in minima_holder:
            diff_array = minima - new_minima
            diff_array_reduced = np.array([np.mod(x,2*np.pi) for x in diff_array])
            elem_bool = True
            for elem in diff_array_reduced:
                # if every element is zero or 2pi, then we have a repeated minima
                elem_bool = elem_bool and (np.allclose(elem,0.0,atol=1e-3) 
                                           or np.allclose(elem,2*np.pi,atol=1e-3))
            if elem_bool:
                new_minima_bool = False
                break
        return new_minima_bool
    
    def _ramp(self, k, minima_holder):
        """
        Helper function for find_minima, performing the ramp that
        is described in Sec. III E of [0]
        
        [0] PRB ...
        """
        guess = np.array([1.15*2.0*np.pi*k/3.0,2.0*np.pi*k/3.0])
        result = minimize(self.potential, guess)
        new_minima = self._check_if_new_minima(result.x, minima_holder)
        if new_minima:
            minima_holder.append(np.array([np.mod(elem,2*np.pi) for elem in result.x]))
        return (minima_holder, new_minima)
    
    def find_minima(self):
        """
        Index all minima in the variable space of phi1 and phi2
        """
        minima_holder = []
        if self.flux == 0.5:
            guess = np.array([0.15,0.1])
        else:
            guess = np.array([0.0,0.0])
        result = minimize(self.potential,guess)
        minima_holder.append(np.array([np.mod(elem,2*np.pi) for elem in result.x]))
        k = 0
        for k in range(1,4):
            (minima_holder, new_minima_positive) = self._ramp(k, minima_holder)
            (minima_holder, new_minima_negative) = self._ramp(-k, minima_holder)
            if not (new_minima_positive and new_minima_negative):
                break
        return(minima_holder)
    
    def sorted_minima(self):
        """Sort the minima based on the value of the potential at the minima """
        minima_holder = self.find_minima()
        value_of_potential = np.array([self.potential(minima_holder[x]) 
                                       for x in range(len(minima_holder))])
        sorted_minima_holder = np.array([x for _, x in 
                                         sorted(zip(value_of_potential, minima_holder))])
        return sorted_minima_holder
    
    def hamiltonian(self):
        """Construct the Hamiltonian"""
        return (self.kineticmat() + self.potentialmat())
    
    def _evals_calc(self, evals_count):
        hamiltonian_mat = self.hamiltonian()
        inner_product_mat = self.inner_product()
        try:
            evals = sp.linalg.eigh(hamiltonian_mat, b=inner_product_mat, 
                                   eigvals_only=True, eigvals=(0, evals_count - 1))
        except LinAlgError:
            print("exception")
            global_min = self.sorted_minima()[0]
            global_min_value = self.potential(global_min)
            evals = sp.sparse.linalg.eigsh(hamiltonian_mat, k=evals_count, M=inner_product_mat, 
                                           sigma=global_min_value, which='LM', return_eigenvectors=False)
        return np.sort(evals)

    def _esys_calc(self, evals_count):
        hamiltonian_mat = self.hamiltonian()
        inner_product_mat = self.inner_product()
        try:
            evals, evecs = sp.linalg.eigh(hamiltonian_mat, b=inner_product_mat,
                                          eigvals_only=False, eigvals=(0, evals_count - 1))
            evals, evecs = order_eigensystem(evals, evecs)
        except LinAlgError:
            print("exception")
            global_min = self.sorted_minima()[0]
            global_min_value = self.potential(global_min)
            evals, evecs = sp.sparse.linalg.eigsh(hamiltonian_mat, k=evals_count, M=inner_product_mat, 
                                                  sigma=global_min_value, return_eigenvectors=True)
            evals, evecs = order_eigensystem(evals, evecs)
        return evals, evecs

    def inner_product(self):
        dim = self.hilbertdim()
        identity_test_mat = np.zeros((dim,dim))
        minima_list = self.sorted_minima()
        Xi = self.Xi_matrix()
        Xi_inv = sp.linalg.inv(Xi)
        EC_mat = self.build_EC_matrix()
        EC_mat_t = np.matmul(Xi_inv,np.matmul(EC_mat,np.transpose(Xi_inv)))
        for m, minima_m in enumerate(minima_list):
            for p, minima_p in enumerate(minima_list):
                for sone in range(self.num_exc+1):
                    for stwo in range(self.num_exc+1):
                        for soneprime in range(self.num_exc+1):
                            for stwoprime in range(self.num_exc+1):
                                klist = itertools.product(np.arange(-self.kmax, self.kmax + 1), repeat=2)
                                jkvals = next(klist,-1)
                                matelem = 0.
                                while jkvals != -1:
                                    phik = 2.0*np.pi*np.array([jkvals[0],jkvals[1]])
                                    zetaoneoffset = Xi_inv[0,0]*minima_m[0]+Xi_inv[0,1]*minima_m[1]
                                    zetatwooffset = Xi_inv[1,0]*minima_m[0]+Xi_inv[1,1]*minima_m[1]
                                    zetaoneprimeoffset = (Xi_inv[0,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[0,1]*(phik[1]+minima_p[1]))
                                    zetatwoprimeoffset = (Xi_inv[1,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[1,1]*(phik[1]+minima_p[1]))
                                    matelem += (np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                       c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                       alpha=zetatwooffset+zetatwoprimeoffset)
                                                * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, 
                                                      b=-2*zetaoneoffset, c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                      alpha=zetaoneoffset+zetaoneprimeoffset)
                                                * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    jkvals = next(klist, -1)
                                i = (self.num_exc+1)*(sone)+stwo+m*(self.num_exc+1)**2
                                j = (self.num_exc+1)*(soneprime)+stwoprime+p*(self.num_exc+1)**2
                                identity_test_mat[i, j] += matelem
        return(identity_test_mat)
    
    def potentialmat(self):
        dim = self.hilbertdim()
        potential_test_mat = np.zeros((dim,dim), dtype=np.complex_)
        minima_list = self.sorted_minima()
        Xi = self.Xi_matrix()
        Xi_inv = sp.linalg.inv(Xi)
        for m, minima_m in enumerate(minima_list):
            for p, minima_p in enumerate(minima_list):
                for sone in range(self.num_exc+1):
                    for stwo in range(self.num_exc+1):
                        for soneprime in range(self.num_exc+1):
                            for stwoprime in range(self.num_exc+1):
                                klist = itertools.product(np.arange(-self.kmax, self.kmax + 1), repeat=2)
                                jkvals = next(klist,-1)
                                matelem = 0.0
                                while jkvals != -1:
                                    phik = 2.0*np.pi*np.array([jkvals[0],jkvals[1]])
                                    zetaoneoffset = Xi_inv[0,0]*minima_m[0]+Xi_inv[0,1]*minima_m[1]
                                    zetatwooffset = Xi_inv[1,0]*minima_m[0]+Xi_inv[1,1]*minima_m[1]
                                    zetaoneprimeoffset = (Xi_inv[0,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[0,1]*(phik[1]+minima_p[1]))
                                    zetatwoprimeoffset = (Xi_inv[1,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[1,1]*(phik[1]+minima_p[1]))
                                    
                                    potential1pos = -0.5*self.EJ*(np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                                  * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetatwooffset,c=2, 
                                                                         d=-2*zetatwoprimeoffset, f=1, 
                                                                         alpha=(zetatwooffset+zetatwoprimeoffset
                                                                                + 1j*Xi[0, 1]))
                                                                  * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetaoneoffset, c=2, 
                                                                         d=-2*zetaoneprimeoffset, f=1, 
                                                                         alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                               + 1j*Xi[0, 0]))
                                                                  * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    potential1neg = -0.5*self.EJ*(np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                                  * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetatwooffset,c=2, 
                                                                         d=-2*zetatwoprimeoffset, f=1, 
                                                                         alpha=(zetatwooffset+zetatwoprimeoffset
                                                                               - 1j*Xi[0, 1]))
                                                                  * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetaoneoffset, c=2, 
                                                                         d=-2*zetaoneprimeoffset, f=1, 
                                                                         alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                               - 1j*Xi[0, 0]))
                                                                  * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    potential2pos = -0.5*self.EJ*(np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                                  * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetatwooffset,c=2, 
                                                                         d=-2*zetatwoprimeoffset, f=1, 
                                                                         alpha=(zetatwooffset+zetatwoprimeoffset
                                                                               + 1j*Xi[1, 1]))
                                                                  * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetaoneoffset, c=2, 
                                                                         d=-2*zetaoneprimeoffset, f=1, 
                                                                         alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                               + 1j*Xi[1, 0]))
                                                                  * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    potential2neg = -0.5*self.EJ*(np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                                  * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetatwooffset,c=2, 
                                                                         d=-2*zetatwoprimeoffset, f=1, 
                                                                         alpha=(zetatwooffset+zetatwoprimeoffset
                                                                               - 1j*Xi[1, 1]))
                                                                  * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                                         a=2, b=-2*zetaoneoffset, c=2, 
                                                                         d=-2*zetaoneprimeoffset, f=1, 
                                                                         alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                               - 1j*Xi[1, 0]))
                                                                  * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    potential3pos = -(0.5*self.alpha*self.EJ*np.exp(-1j*2.0*np.pi*self.flux)
                                                      * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                      * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                             a=2, b=-2*zetatwooffset,c=2, 
                                                             d=-2*zetatwoprimeoffset, f=1, 
                                                             alpha=(zetatwooffset+zetatwoprimeoffset
                                                                    + 1j*(Xi[1, 1] - Xi[0, 1])))
                                                      * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                             a=2, b=-2*zetaoneoffset, c=2, 
                                                             d=-2*zetaoneprimeoffset, f=1, 
                                                             alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                    + 1j*(Xi[1, 0] - Xi[0, 0])))
                                                      * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    potential3neg = -(0.5*self.alpha*self.EJ*np.exp(1j*2.0*np.pi*self.flux)
                                                      * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                      * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, 
                                                             a=2, b=-2*zetatwooffset,c=2, 
                                                             d=-2*zetatwoprimeoffset, f=1, 
                                                             alpha=(zetatwooffset+zetatwoprimeoffset
                                                                    - 1j*(Xi[1, 1] - Xi[0, 1])))
                                                      * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, 
                                                             a=2, b=-2*zetaoneoffset, c=2, 
                                                             d=-2*zetaoneprimeoffset, f=1, 
                                                             alpha=(zetaoneoffset+zetaoneprimeoffset
                                                                    - 1j*(Xi[1, 0] - Xi[0, 0])))
                                                      * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    matelem += (potential1pos + potential1neg + potential2pos
                                               + potential2neg + potential3pos + potential3neg)
                                    i = (self.num_exc+1)*(sone)+stwo+m*(self.num_exc+1)**2
                                    j = (self.num_exc+1)*(soneprime)+stwoprime+p*(self.num_exc+1)**2
#                                    if ((i==6) and (j==0)):
#                                        print(potential1pos, potential1neg, potential2pos, 
#                                              potential2neg, potential3pos, potential3neg)
#                                        print(matelem, "jkvals = ", jkvals)

                                    
                                    jkvals = next(klist, -1)
                                i = (self.num_exc+1)*(sone)+stwo+m*(self.num_exc+1)**2
                                j = (self.num_exc+1)*(soneprime)+stwoprime+p*(self.num_exc+1)**2
                                potential_test_mat[i, j] += matelem
        return(potential_test_mat)
        
    def kineticmat(self):
        dim = self.hilbertdim()
        kinetic_test_mat = np.zeros((dim,dim))
        minima_list = self.sorted_minima()
        Xi = self.Xi_matrix()
        Xi_inv = sp.linalg.inv(Xi)
        EC_mat = self.build_EC_matrix()
        EC_mat_t = np.matmul(Xi_inv,np.matmul(EC_mat,np.transpose(Xi_inv)))
        for m, minima_m in enumerate(minima_list):
            for p, minima_p in enumerate(minima_list):
                for sone in range(self.num_exc+1):
                    for stwo in range(self.num_exc+1):
                        for soneprime in range(self.num_exc+1):
                            for stwoprime in range(self.num_exc+1):
                                klist = itertools.product(np.arange(-self.kmax, self.kmax + 1), repeat=2)
                                jkvals = next(klist,-1)
                                matelem = 0.0
                                while jkvals != -1:
                                    phik = 2.0*np.pi*np.array([jkvals[0],jkvals[1]])
                                    zetaoneoffset = Xi_inv[0,0]*minima_m[0]+Xi_inv[0,1]*minima_m[1]
                                    zetatwooffset = Xi_inv[1,0]*minima_m[0]+Xi_inv[1,1]*minima_m[1]
                                    zetaoneprimeoffset = (Xi_inv[0,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[0,1]*(phik[1]+minima_p[1]))
                                    zetatwoprimeoffset = (Xi_inv[1,0]*(phik[0]+minima_p[0])
                                                          + Xi_inv[1,1]*(phik[1]+minima_p[1]))
                                    
                                    elem11 = (4.0*EC_mat_t[0, 0]
                                                * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                       c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                       alpha=zetatwooffset+zetatwoprimeoffset)
                                                * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, 
                                                      b=-2*zetaoneoffset, c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                      alpha=zetaoneoffset+zetaoneprimeoffset)
                                                * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                                                        
                                    elem12 = -(4.0*EC_mat_t[0, 0]
                                                 * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                 * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                        c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                        alpha=zetatwooffset+zetatwoprimeoffset)
                                                 * pImn(p=2, m=sone, n=soneprime, y=-1, z=-1, a=2, 
                                                        b=-2*(zetaoneoffset-zetaoneprimeoffset), c=2, 
                                                        d=0, f=1, alpha=zetaoneoffset-zetaoneprimeoffset)
                                                 * np.exp(-0.5*(zetaoneprimeoffset-zetaoneoffset)**2))
                                                                        
                                    elem13 = elem14 = 0.
                                    if soneprime >= 1:
                                        elem13 += -((4.0*EC_mat_t[0, 0]/(np.sqrt(soneprime*2)))
                                                     * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                     * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                           c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                           alpha=zetatwooffset+zetatwoprimeoffset)
                                                     * 4*zetaoneprimeoffset*soneprime
                                                     * pImn(p=0, m=sone, n=soneprime-1, y=-1, z=-1, a=2, 
                                                           b=-2*zetaoneoffset, c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                           alpha=zetaoneoffset+zetaoneprimeoffset)
                                                     * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                        
                                        elem14 += ((4.0*EC_mat_t[0, 0]/(np.sqrt(soneprime*2)))
                                                    * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                    * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                           c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                           alpha=zetatwooffset+zetatwoprimeoffset)
                                                    * 4*soneprime
                                                    * pImn(p=1, m=sone, n=soneprime-1, y=-1, z=-1, a=2, 
                                                          b=-2*zetaoneoffset, c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                          alpha=zetaoneoffset+zetaoneprimeoffset)
                                                    * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                    
                                    elem15 = 0.
                                    if soneprime >= 2:
                                        elem15 += (-(4.0*EC_mat_t[0, 0]/(np.sqrt(soneprime*(soneprime-1)*2*2)))
                                                   * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2))
                                                   * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, b=-2*zetatwooffset,
                                                       c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                        alpha=zetatwooffset+zetatwoprimeoffset)
                                                   * 4*soneprime*(soneprime - 1)
                                                   * pImn(p=0, m=sone, n=soneprime-2, y=-1, z=-1, a=2, 
                                                          b=-2*zetaoneoffset, c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                          alpha=zetaoneoffset+zetaoneprimeoffset)
                                                   * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2)))
                                        
                                    #########
                                    
                                    elem21 = (4.0*EC_mat_t[1, 1]
                                                * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2))
                                                * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, b=-2*zetaoneoffset,
                                                       c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                       alpha=zetaoneoffset+zetaoneprimeoffset)
                                                * pImn(p=0, m=stwo, n=stwoprime, y=-1, z=-1, a=2, 
                                                      b=-2*zetatwooffset, c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                      alpha=zetatwooffset+zetatwoprimeoffset)
                                                * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2)))
                                    
                                    elem22 = -(4.0*EC_mat_t[1, 1]
                                                 * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2))
                                                 * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, b=-2*zetaoneoffset,
                                                        c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                        alpha=zetaoneoffset+zetaoneprimeoffset)
                                                 * pImn(p=2, m=stwo, n=stwoprime, y=-1, z=-1, a=2, 
                                                        b=-2*(zetatwooffset-zetatwoprimeoffset), c=2, 
                                                        d=0, f=1, alpha=zetatwooffset-zetatwoprimeoffset)
                                                 * np.exp(-0.5*(zetatwoprimeoffset-zetatwooffset)**2))
                                    
                                    elem23 = elem24 = 0.
                                    if stwoprime >= 1:
                                        elem23 += -((4.0*EC_mat_t[1, 1]/(np.sqrt(stwoprime*2)))
                                                     * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2))
                                                     * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, b=-2*zetaoneoffset,
                                                            c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                            alpha=zetaoneoffset+zetaoneprimeoffset)
                                                     * 4*zetatwoprimeoffset*stwoprime
                                                     * pImn(p=0, m=stwo, n=stwoprime-1, y=-1, z=-1, a=2, 
                                                           b=-2*zetatwooffset, c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                           alpha=zetatwooffset+zetatwoprimeoffset)
                                                     * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2)))
                                        
                                        elem24 += ((4.0*EC_mat_t[1, 1]/(np.sqrt(stwoprime*2)))
                                                    * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2))
                                                    * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, b=-2*zetaoneoffset,
                                                           c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                           alpha=zetaoneoffset+zetaoneprimeoffset)
                                                    * 4*stwoprime
                                                    * pImn(p=1, m=stwo, n=stwoprime-1, y=-1, z=-1, a=2, 
                                                          b=-2*zetatwooffset, c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                          alpha=zetatwooffset+zetatwoprimeoffset)
                                                    * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2)))
                                    
                                    elem25 = 0.
                                    if stwoprime >= 2:
                                        elem25 += (-(4.0*EC_mat_t[1, 1]/(np.sqrt(stwoprime*(stwoprime-1)*2*2)))
                                                   * np.exp(-0.5*(zetaoneoffset**2 + zetaoneprimeoffset**2))
                                                   * pImn(p=0, m=sone, n=soneprime, y=-1, z=-1, a=2, b=-2*zetaoneoffset,
                                                          c=2, d=-2*zetaoneprimeoffset, f=1, 
                                                          alpha=zetaoneoffset+zetaoneprimeoffset)
                                                   * 4*stwoprime*(stwoprime - 1)
                                                   * pImn(p=0, m=stwo, n=stwoprime-2, y=-1, z=-1, a=2, 
                                                          b=-2*zetatwooffset, c=2, d=-2*zetatwoprimeoffset, f=1, 
                                                          alpha=zetatwooffset+zetatwoprimeoffset)
                                                   * np.exp(-0.5*(zetatwooffset**2 + zetatwoprimeoffset**2)))
                                        
                                    matelem += (elem11 + elem12 + elem13 + elem14 + elem15
                                                + elem21 + elem22 + elem23 + elem24 + elem25)
                                    i = (self.num_exc+1)*(sone)+stwo+m*(self.num_exc+1)**2
                                    j = (self.num_exc+1)*(soneprime)+stwoprime+p*(self.num_exc+1)**2
#                                    if ((i==0) and (j==4)):
#                                        print(elem11, elem12, elem13, elem14, elem15,
#                                              elem21, elem22, elem23, elem24, elem25)
#                                        print(matelem, "jkvals = ", jkvals, "babusci")
                                    jkvals = next(klist, -1)
                                i = (self.num_exc+1)*(sone)+stwo+m*(self.num_exc+1)**2
                                j = (self.num_exc+1)*(soneprime)+stwoprime+p*(self.num_exc+1)**2
                                kinetic_test_mat[i, j] += matelem
        return(kinetic_test_mat)        



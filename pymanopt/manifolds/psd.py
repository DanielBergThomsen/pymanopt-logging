import numpy as np
from numpy import linalg as la
from numpy import random as rnd
from scipy.linalg import solve_continuous_lyapunov as lyap

from pymanopt.manifolds.manifold import Manifold, RetrAsExpMixin


# TODO(nkoep): This could either stay in here (seeing how it's a manifold of
#              psd matrices, or in fixed_rank. Alternatively, move this one and
#              the next class to a dedicated 'psd_fixed_rank' module.


class _PSDFixedRank(Manifold, RetrAsExpMixin):
    def __init__(self, n, k, name, dimension):
        self._n = n
        self._k = k
        super().__init__(name, dimension)

    @property
    def typicaldist(self):
        return 10 + self._k

    def inner(self, Y, U, V):
        # Euclidean metric on the total space.
        return float(np.tensordot(U, V))

    def norm(self, Y, U):
        return la.norm(U, "fro")

    def proj(self, Y, H):
        # Projection onto the horizontal space
        YtY = Y.T @ Y
        AS = Y.T @ H - H.T @ Y
        Omega = lyap(YtY, AS)
        return H - Y @ Omega

    def egrad2rgrad(self, Y, egrad):
        return egrad

    def ehess2rhess(self, Y, egrad, ehess, U):
        return self.proj(Y, ehess)

    def retr(self, Y, U):
        return Y + U

    def rand(self):
        return rnd.randn(self._n, self._k)

    def randvec(self, Y):
        H = self.rand()
        P = self.proj(Y, H)
        return self._normalize(P)

    def transp(self, Y, Z, U):
        return self.proj(Z, U)

    def _normalize(self, Y):
        return Y / self.norm(None, Y)

    def zerovec(self, X):
        return np.zeros((self._n, self._k))


class PSDFixedRank(_PSDFixedRank):
    """Manifold of fixed-rank positive semidefinite (PSD) matrices.

    A point X on the manifold is parameterized as YY^T where Y is a matrix of
    size nxk. As such, X is symmetric, positive semidefinite. We restrict to
    full-rank Y's, such that X has rank exactly k. The point X is numerically
    represented by Y (this is more efficient than working with X, which may
    be big). Tangent vectors are represented as matrices of the same size as
    Y, call them Ydot, so that Xdot = Y Ydot' + Ydot Y. The metric is the
    canonical Euclidean metric on Y.

    Since for any orthogonal Q of size k, it holds that (YQ)(YQ)' = YY',
    we "group" all matrices of the form YQ in an equivalence class. The set
    of equivalence classes is a Riemannian quotient manifold, implemented
    here.

    Notice that this manifold is not complete: if optimization leads Y to be
    rank-deficient, the geometry will break down. Hence, this geometry should
    only be used if it is expected that the points of interest will have rank
    exactly k. Reduce k if that is not the case.

    An alternative, complete, geometry for positive semidefinite matrices of
    rank k is described in Bonnabel and Sepulchre 2009, "Riemannian Metric
    and Geometric Mean for Positive Semidefinite Matrices of Fixed Rank",
    SIAM Journal on Matrix Analysis and Applications.

    The geometry implemented here is the simplest case of the 2010 paper:
    M. Journee, P.-A. Absil, F. Bach and R. Sepulchre,
    "Low-Rank Optimization on the Cone of Positive Semidefinite Matrices".
    Paper link: http://www.di.ens.fr/~fbach/journee2010_sdp.pdf
    """

    def __init__(self, n, k):
        name = f"Quotient manifold of {n}x{n} psd matrices of rank {k}"
        dimension = int(k * n - k * (k - 1) / 2)
        super().__init__(n, k, name, dimension)


class PSDFixedRankComplex(_PSDFixedRank):
    """Manifold of fixed-rank Hermitian positive semidefinite (PSD) matrices.

    Manifold of n-by-n complex Hermitian positive semidefinite matrices of
    fixed rank k. This follows the quotient geometry described
    in Sarod Yatawatta's 2013 paper:
    "Radio interferometric calibration using a Riemannian manifold", ICASSP.

    Paper link: http://dx.doi.org/10.1109/ICASSP.2013.6638382.

    A point X on the manifold M is parameterized as YY^*, where Y is a
    complex matrix of size nxk of full rank. For any point Y on the manifold M,
    given any kxk complex unitary matrix U, we say Y*U  is equivalent to Y,
    i.e., YY^* does not change. Therefore, M is the set of equivalence
    classes and is a Riemannian quotient manifold C^{nk}/U(k)
    where C^{nk} is the set of all complex matrix of size nxk of full rank.
    The metric is the usual real-trace inner product, that is,
    it is the usual metric for the complex plane identified with R^2.

    Notice that this manifold is not complete: if optimization leads Y to be
    rank-deficient, the geometry will break down. Hence, this geometry should
    only be used if it is expected that the points of interest will have rank
    exactly k. Reduce k if that is not the case.
    """

    def __init__(self, n, k):
        name = f"Quotient manifold of Hermitian {n}x{n} matrices of rank {k}"
        dimension = 2 * k * n - k * k
        super().__init__(n, k, name, dimension)

    def inner(self, Y, U, V):
        return 2 * float(np.tensordot(U, V).real)

    def norm(self, Y, U):
        return np.sqrt(self.inner(Y, U, U))

    def dist(self, U, V):
        S, _, D = la.svd(V.T.conj() @ U)
        E = U - V @ S @ D
        return self.inner(None, E, E) / 2

    def rand(self):
        rand_ = super().rand
        return rand_() + 1j * rand_()


class Elliptope(Manifold, RetrAsExpMixin):
    """Manifold of fixed-rank PSD matrices with unit diagonal elements.

    A point X on the manifold is parameterized as YY^T where Y is a matrix of
    size nxk. As such, X is symmetric, positive semidefinite. We restrict to
    full-rank Y's, such that X has rank exactly k. The point X is numerically
    represented by Y (this is more efficient than working with X, which may be
    big). Tangent vectors are represented as matrices of the same size as Y,
    call them Ydot, so that Xdot = Y Ydot' + Ydot Y and diag(Xdot) == 0. The
    metric is the canonical Euclidean metric on Y.

    The diagonal constraints on X (X(i, i) == 1 for all i) translate to
    unit-norm constraints on the rows of Y: norm(Y(i, :)) == 1 for all i.  The
    set of such Y's forms the oblique manifold. But because for any orthogonal
    Q of size k, it holds that (YQ)(YQ)' = YY', we "group" all matrices of the
    form YQ in an equivalence class. The set of equivalence classes is a
    Riemannian quotient manifold, implemented here.

    Note that this geometry formally breaks down at rank-deficient Y's.  This
    does not appear to be a major issue in practice when optimization
    algorithms converge to rank-deficient Y's, but convergence theorems no
    longer hold. As an alternative, you may use the oblique manifold (it has
    larger dimension, but does not break down at rank drop.)

    The geometry is taken from the 2010 paper:
    M. Journee, P.-A. Absil, F. Bach and R. Sepulchre,
    "Low-Rank Optimization on the Cone of Positive Semidefinite Matrices".
    Paper link: http://www.di.ens.fr/~fbach/journee2010_sdp.pdf
    """

    def __init__(self, n, k):
        self._n = n
        self._k = k

        name = (
            f"Quotient manifold of {n}x{n} psd matrices of rank {k} "
            "with unit diagonal elements"
        )
        dimension = int(n * (k - 1) - k * (k - 1) / 2)
        super().__init__(name, dimension)

    @property
    def typicaldist(self):
        return 10 * self._k

    def inner(self, Y, U, V):
        return float(np.tensordot(U, V))

    def norm(self, Y, U):
        return np.sqrt(self.inner(Y, U, U))

    # Projection onto the tangent space, i.e., on the tangent space of
    # ||Y[i, :]||_2 = 1
    def proj(self, Y, H):
        eta = self._project_rows(Y, H)

        # Projection onto the horizontal space
        YtY = Y.T @ Y
        AS = Y.T @ eta - H.T @ Y
        Omega = lyap(YtY, -AS)
        return eta - Y @ (Omega - Omega.T) / 2

    def retr(self, Y, U):
        return self._normalize_rows(Y + U)

    # Euclidean gradient to Riemannian gradient conversion. We only need the
    # ambient space projection: the remainder of the projection function is not
    # necessary because the Euclidean gradient must already be orthogonal to
    # the vertical space.
    def egrad2rgrad(self, Y, egrad):
        return self._project_rows(Y, egrad)

    def ehess2rhess(self, Y, egrad, ehess, U):
        scaling_grad = (egrad * Y).sum(axis=1)
        hess = ehess - U * scaling_grad[:, np.newaxis]

        scaling_hess = (U * egrad + Y * ehess).sum(axis=1)
        hess -= Y * scaling_hess[:, np.newaxis]

        return self.proj(Y, hess)

    def rand(self):
        return self._normalize_rows(rnd.randn(self._n, self._k))

    def randvec(self, Y):
        H = self.proj(Y, self.rand())
        return H / self.norm(Y, H)

    def transp(self, Y, Z, U):
        return self.proj(Z, U)

    def _normalize_rows(self, Y):
        """Return an l2-row-normalized copy of the matrix Y."""
        return Y / la.norm(Y, axis=1)[:, np.newaxis]

    # Orthogonal projection of each row of H to the tangent space at the
    # corresponding row of X, seen as a point on a sphere.
    def _project_rows(self, Y, H):
        # Compute the inner product between each vector H[i, :] with its root
        # point Y[i, :], i.e., Y[i, :].T * H[i, :]. Returns a row vector.
        inners = (Y * H).sum(axis=1)
        return H - Y * inners[:, np.newaxis]

    def zerovec(self, X):
        return np.zeros((self._n, self._k))

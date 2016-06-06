import os
from itertools import combinations, product
from multiprocessing import Pool
from timeit import default_timer as timer

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from scipy.stats import pearsonr


class ROIFinder:
    # toy data specifics
    TOY_DIM = 10  # cube size
    N_TOY_SUBJECTS = 5
    TOY_LOW = - 10
    TOY_UP = abs(TOY_LOW)
    # 3d directions to find neighbor voxels
    DIRECTIONS = dict(front=np.array([-1, 0, 0]), back=np.array([1, 0, 0]),
                      top=np.array([0, -1, 0]), bottom=np.array([0, 1, 0]),
                      left=np.array([0, 0, -1]), right=np.array([0, 0, 1]))

    # correlation thresholds
    R_THRESHOLD = 0.5
    P_TRESHOLD = 0.005
    # number of CPUs for multiprocessing
    N_CPUS = os.cpu_count()

    def __init__(self, volumes=None, r_threshold=R_THRESHOLD,
                 p_threshold=P_TRESHOLD, n_jobs=1, min_cluster_size=2,
                 random_seed=None):

        if random_seed is not None:
                np.random.seed(random_seed)

        if volumes is not None:
            # check if volumes are provided as 4d array or list of 3d arrays
            if isinstance(volumes, np.ndarray):
                n_subjects = volumes.shape[0]
                self.volumes = [volumes[s, ...] for s in range(n_subjects)]
            elif isinstance(volumes, list):
                self.volumes = volumes
            elif isinstance(volumes, int):
                self.volumes = self.make_toy_data(dim=volumes)
        elif volumes is None:
            self.volumes = self.make_toy_data()

        # shape of the first volume, assumes all volumes have same shape
        self.volume_shape = self.volumes[0].shape
        # arbitrary threshold for pearson coefficient
        self.r_threshold = r_threshold
        # arbitrary threshold for p-value of pearson test
        self.p_threshold = p_threshold
        # filter out clusters smaller than that
        self.min_cluster_size = min_cluster_size
        # number of jobs for multiprocessing
        self.n_jobs = n_jobs if n_jobs <= self.N_CPUS else self.N_CPUS
        # array that contains integers that indicate clusters
        self.cluster_array = np.zeros(self.volume_shape, dtype=int)

    @staticmethod
    def make_toy_data(dim=TOY_DIM, n_subjects=N_TOY_SUBJECTS,
                      lower_bound=TOY_LOW, upper_bound=TOY_UP):
        # random volumes for testing
        low, up = lower_bound, upper_bound
        toy_volumes = [(up - low) * np.random.random_sample(tuple([dim] * 3)) +
                       low for _ in range(n_subjects)]
        return toy_volumes

    def get_neighbor_indices(self, center_index):
        center = list(center_index)
        neighbor_indices = dict()
        for key, val in self.DIRECTIONS.items():
            coord = np.array(center) + val
            coord = self._index_check(coord)
            if coord is not None:
                neighbor_indices[key] = coord
        return neighbor_indices

    def _index_check(self, indices):
        idx_list = list(indices)
        for i, n in enumerate(idx_list):
            if (n < 0) or (n > self.volume_shape[i] - 1):
                return None
        return indices

    def get_neighbor_voxels(self, indices):
        neighbor_voxels = dict()
        for key, val in indices.items():
            index = tuple(val)
            voxels = self.get_voxels(index)
            neighbor_voxels[key] = voxels
        return neighbor_voxels

    def get_voxels(self, index):
        return np.array([v[index] for v in self.volumes])

    def compute_correlation(self, center_voxels, neighbor_voxels):
        correlation_scores = dict()
        for key, val in neighbor_voxels.items():
            r, p = pearsonr(center_voxels, val)
            # filter according to threshold levels for r and p
            if (abs(r) > self.r_threshold) and (p <= self.p_threshold):
                correlation_scores[key] = r, p
        return correlation_scores

    def update_cluster_array(self, correlation_scores, center_idx,
                             neighbor_indices):
        # check how many values are stored in the correlation array and filter
        # out cluster that are smaller than the threshold
        if len(correlation_scores) >= self.min_cluster_size:
            for key, val in correlation_scores.items():
                r, p = val
                idx = tuple(neighbor_indices[key])
                # todo --> mark individual clusters with different integers
                # maybe filter out clusters that only span 2 voxels
                self.cluster_array[idx] = 1
                self.cluster_array[center_idx] = 2

            # if self.cluster_array[center_idx] == 0:
            #     self.cluster_array[center_idx] = 2

    def find_clusters(self):
        if self.n_jobs >= 1:
            for index in np.ndindex(self.volume_shape):
                self._compute_clusters(index)
        # elif self.n_jobs > 1:

            # try:
            #     pool = Pool(processes=self.n_jobs)
            #     pool.map(self._compute_clusters, [index for index in
            #                                   np.ndindex(self.volume_shape)])
            # finally:
            #     pool.close()
            #     pool.join()

    def _compute_clusters(self, index):
        # collect center voxel from all volumes
        center_index = index
        center_voxels = self.get_voxels(center_index)
        # get neighboring voxel indices
        neighbor_indices = self.get_neighbor_indices(center_index)
        # extract voxel values for neighbors
        neighbor_voxels = self.get_neighbor_voxels(neighbor_indices)
        # Pearson with surrounding voxels
        correlation_scores = self.compute_correlation(center_voxels,
                                                      neighbor_voxels)
        self.update_cluster_array(correlation_scores, center_index,
                                  neighbor_indices)

    def draw_clusters(self, ax=None, cubes=False):
        if ax is None:
            ax = plt.gca()
        else:
            ax = ax
        x, z, y = self.cluster_array.nonzero()
        if not cubes:
            ax.scatter(x, y, z, zdir='z', c='red')
        elif cubes:
            cube_coords = list(np.vstack([x, y, z]).T)
            for c in cube_coords:
                self._draw_cube(c, ax=ax)
        return ax

    @staticmethod
    def _draw_cube(coords, ax):
        x, y, z = tuple(coords)
        x_span = [x, x + 1]
        y_span = [y, y + 1]
        z_span = [z, z - 1]
        for s, e in combinations(np.array(list(product(x_span,
                                                       y_span,
                                                       z_span))), 2):
            if np.sum(np.abs(s - e)) == 1:
                ax.plot(*zip(s, e), color="black")
        return ax

if __name__ == '__main__':
    dim=10
    RF = ROIFinder(volumes=dim, r_threshold=0.5, p_threshold=0.05,
                   min_cluster_size=2)
    start = timer()
    clusters = RF.find_clusters()
    end = timer()
    #print((end - start))
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection='3d')
    RF.draw_clusters(ax=ax, cubes=True)
    ax.set_xlabel('Depth (x)')
    ax.set_xlim(0, dim)
    ax.invert_xaxis()

    ax.set_ylabel('Columns (y)')
    ax.set_ylim(0, dim)

    ax.set_zlabel('Rows (z)')
    ax.set_zlim(0, dim)
    ax.invert_zaxis()
    print(RF.cluster_array)

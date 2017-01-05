from rllab.envs.base import Step
from rllab.misc.overrides import overrides
# from rllab.envs.mujoco.mujoco_env import MujocoEnv
from sandbox.carlos_snn.envs.mujoco.mujoco_env import MujocoEnv_ObsInit as MujocoEnv
import numpy as np
from rllab.core.serializable import Serializable
from rllab.misc import logger
from rllab.misc import autoargs
import gc
from functools import reduce
import os.path as osp
import collections

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt



from rllab import spaces
BIG = 1e6

class SnakeEnv(MujocoEnv, Serializable):
    FILE = 'snake.xml'
    ORI_IND = 2

    @autoargs.arg('ctrl_cost_coeff', type=float,
                  help='cost coefficient for controls')
    def __init__(
            self,
            ctrl_cost_coeff=1e-2,
            ego_obs=False,
            sparse_rew=False,
            *args, **kwargs):
        self.ctrl_cost_coeff = ctrl_cost_coeff
        self.ego_obs = ego_obs
        self.sparse_rew = sparse_rew
        super(SnakeEnv, self).__init__(*args, **kwargs)
        Serializable.quick_init(self, locals())

    def get_current_obs(self):
        if self.ego_obs:
            return np.concatenate([
                self.model.data.qpos.flat[2:],
                self.model.data.qvel.flat,
            ]).reshape(-1)
        else:
            return np.concatenate([
                self.model.data.qpos.flat,
                self.model.data.qvel.flat,
                self.get_body_com("torso").flat,
            ]).reshape(-1)

    def get_ori(self):
        return self.model.data.qpos[self.__class__.ORI_IND]

## hack that I will have to remove!!!  I think I actually don't need it anymore! Check maze_env.py
    @property
    def robot_observation_space(self):
        shp = self.get_current_obs().shape
        ub = BIG * np.ones(shp)
        return spaces.Box(ub * -1, ub)

    @property
    def maze_observation_space(self):
        ub = BIG * np.array(())
        return spaces.Box(ub, ub)

    def step(self, action):
        self.forward_dynamics(action)
        next_obs = self.get_current_obs()
        lb, ub = self.action_bounds
        scaling = (ub - lb) * 0.5
        ctrl_cost = 0.5 * self.ctrl_cost_coeff * np.sum(
            np.square(action / scaling))
        forward_reward = np.linalg.norm(self.get_body_comvel("torso"))  # swimmer has no problem of jumping reward
        reward = forward_reward - ctrl_cost
        done = False
        if self.sparse_rew:
            if abs(self.get_body_com("torso")[0]) > 100.0:
                reward = 1.0
                done = True
            else:
                reward = 0.
        com = np.concatenate([self.get_body_com("torso").flat]).reshape(-1)
        ori = self.get_ori()
        return Step(next_obs, reward, done, com=com, ori=ori)

    @overrides
    def log_diagnostics(self, paths, prefix=''):
        # instead of just path["obs"][-1][-3] we will look at the distance to origin
        progs = [
            # np.linalg.norm(path["observations"][-1][-3:-1] - path["observations"][0][-3:-1])
            np.linalg.norm(path["env_infos"]['com'][-1] - path["env_infos"]['com'][0])
            # gives (x,y) coord -not last z
            for path in paths
            ]
        with logger.tabular_prefix(prefix):
            logger.record_tabular('AverageForwardProgress', np.mean(progs))
            logger.record_tabular('MaxForwardProgress', np.max(progs))
            logger.record_tabular('MinForwardProgress', np.min(progs))
            logger.record_tabular('StdForwardProgress', np.std(progs))

        self.plot_visitation(paths, prefix=prefix)

    def plot_visitation(self, paths, mesh_density=50, maze=None, scaling=2, prefix=''):
        fig, ax = plt.subplots()
        # now we will grid the space and check how much of it the policy is covering
        if self.ego_obs:
            x_max = np.ceil(np.max(np.abs(np.concatenate([path["env_infos"]['com'][:, 0] for path in paths]))))
            y_max = np.ceil(np.max(np.abs(np.concatenate([path["env_infos"]['com'][:, 1] for path in paths]))))
        else:
            x_max = np.ceil(np.max(np.abs(np.concatenate([path["observations"][:, -3] for path in paths]))))
            y_max = np.ceil(np.max(np.abs(np.concatenate([path["observations"][:, -2] for path in paths]))))
        furthest = max(x_max, y_max)
        print('THE FUTHEST IT WENT COMPONENT-WISE IS: x_max={}, y_max={}'.format(x_max, y_max))
        # if maze:
        #     x_max = max(scaling * len(
        #         maze) / 2. - 1, x_max)  # maze enlarge plot to include the walls. ASSUME ROBOT STARTS IN CENTER!
        #     y_max = max(scaling * len(maze[0]) / 2. - 1, y_max)  # the max here should be useless...
        #     print("THE MAZE LIMITS ARE: x_max={}, y_max={}".format(x_max, y_max))
        delta = 1./mesh_density
        y, x = np.mgrid[-furthest:furthest+delta:delta, -furthest:furthest+delta:delta]

        if 'agent_infos' in list(paths[0].keys()) and (('latents' in list(paths[0]['agent_infos'].keys())
                                                        and np.size(paths[0]['agent_infos']['latents'])) or
                                                           ('selectors' in list(paths[0]['agent_infos'].keys())
                                                            and np.size(paths[0]['agent_infos']['selectors']))):
            selectors_name = 'latents' if 'latents' in list(paths[0]['agent_infos'].keys()) else 'selectors'
            dict_visit = collections.OrderedDict()  # keys: latents, values: np.array with number of visitations
            num_latents = np.size(paths[0]["agent_infos"][selectors_name][0])
            # set all the labels for the latents and initialize the entries of dict_visit
            for i in range(num_latents):  # use integer to define the latents
                dict_visit[i] = np.zeros((2 * furthest * mesh_density + 1, 2 * furthest * mesh_density + 1))

            # keep track of the overlap
            overlap = 0
            # now plot all the paths
            for path in paths:
                lats = [np.nonzero(lat)[0][0] for lat in path['agent_infos'][selectors_name]]  # list of all lats by idx
                # if self.ego_obs:
                com_x = np.ceil(((np.array(path['env_infos']['com'][:, 0]) + furthest) * mesh_density)).astype(int)
                com_y = np.ceil(((np.array(path['env_infos']['com'][:, 1]) + furthest) * mesh_density)).astype(int)
                # else:
                #     com_x = np.ceil(((np.array(path['observations'][:, -3]) + furthest) * mesh_density)).astype(int)
                #     com_y = np.ceil(((np.array(path['observations'][:, -2]) + furthest) * mesh_density)).astype(int)
                coms = list(zip(com_x, com_y))
                for i, com in enumerate(coms):
                    dict_visit[lats[i]][com] += 1

            # fix the colors for each latent
            num_colors = num_latents + 2  # +2 for the 0 and Repetitions NOT COUNTING THE WALLS
            cmap = plt.get_cmap('nipy_spectral', num_colors)  # add one color for the walls
            # create a matrix with entries corresponding to the latent that was there (or other if several/wall/nothing)
            visitation_by_lat = np.zeros((2 * furthest * mesh_density + 1, 2 * furthest * mesh_density + 1))
            for i, visit in dict_visit.items():
                lat_visit = np.where(visit == 0, visit, i + 1)  # transform the map into 0 or i+1
                visitation_by_lat += lat_visit
                overlap += np.sum(np.where(visitation_by_lat > lat_visit))  # add the overlaps of this latent
                visitation_by_lat = np.where(visitation_by_lat <= i + 1, visitation_by_lat,
                                             num_colors - 1)  # mark overlaps
            # if maze:
            #     for row in range(len(maze)):
            #         for col in range(len(maze[0])):
            #             if maze[row][col] == 1:
            #                 wall_min_x = max(0, (row - 0.5) * mesh_density * scaling)
            #                 wall_max_x = min(2 * furthest * mesh_density * scaling + 1,
            #                                  (row + 0.5) * mesh_density * scaling)
            #                 wall_min_y = max(0, (col - 0.5) * mesh_density * scaling)
            #                 wall_max_y = min(2 * furthest * mesh_density * scaling + 1,
            #                                  (col + 0.5) * mesh_density * scaling)
            #                 visitation_by_lat[wall_min_x: wall_max_x,
            #                 wall_min_y: wall_max_y] = num_colors
            #     gx_min, gfurthest, gy_min, gfurthest = self._find_goal_range()
            #     ax.add_patch(patches.Rectangle(
            #         (gx_min, gy_min),
            #         gfurthest - gx_min,
            #         gfurthest - gy_min,
            #         edgecolor='g', fill=False, linewidth=2,
            #     ))
            #     ax.annotate('G', xy=(0.5*(gx_min+gfurthest), 0.5*(gy_min+gfurthest)), color='g', fontsize=20)
            map_plot = ax.pcolormesh(x, y, visitation_by_lat, cmap=cmap, vmin=0.1,
                                     vmax=num_latents + 1)  # before 1 (will it affect when no walls?)
            color_len = (num_colors - 1.) / num_colors
            ticks = np.arange(color_len / 2., num_colors - 1, color_len)
            cbar = fig.colorbar(map_plot, ticks=ticks)
            latent_tick_labels = ['latent: ' + str(i) for i in list(dict_visit.keys())]
            cbar.ax.set_yticklabels(
                ['No visitation'] + latent_tick_labels + ['Repetitions'])  # horizontal colorbar
            # still log the total visitation
            visitation_all = reduce(np.add, [visit for visit in dict_visit.values()])
        else:
            visitation_all = np.zeros((2 * furthest * mesh_density + 1, 2 * furthest * mesh_density + 1))
            for path in paths:
                com_x = np.ceil(((np.array(path['env_infos']['com'][:, 0]) + furthest) * mesh_density)).astype(int)
                com_y = np.ceil(((np.array(path['env_infos']['com'][:, 1]) + furthest) * mesh_density)).astype(int)
                coms = list(zip(com_x, com_y))
                for com in coms:
                    visitation_all[com] += 1

            plt.pcolormesh(x, y, visitation_all, vmax=mesh_density)
            overlap = np.sum(np.where(visitation_all > 1, visitation_all, 0))  # sum of all visitations larger than 1

        ax.set_xlim([x[0][0], x[0][-1]])
        ax.set_ylim([y[0][0], y[-1][0]])

        log_dir = logger.get_snapshot_dir()
        exp_name = log_dir.split('/')[-1] if log_dir else '?'
        ax.set_title(prefix + 'visitation: ' + exp_name)

        plt.savefig(osp.join(log_dir, prefix + 'visitation.png'))  # this saves the current figure, here f
        plt.close()

        radius_furthest075 = {True: 1e-6, False: 1}
        radius_furthest05 = {True: 1e-6, False: 1}
        radius_5 = {True: 1e-6, False: 1}

        for i, row in enumerate(visitation_all):
            for j, cell in enumerate(row):
                dist_to_origin = np.sqrt((i * delta - furthest) ** 2 + (j * delta - furthest) ** 2)
                if 0.75 * furthest - delta < dist_to_origin < 0.75 * furthest + delta:
                    radius_furthest075[bool(visitation_all[i, j])] += 1
                if 0.5 * furthest - delta < dist_to_origin < 0.5 * furthest + delta:
                    radius_furthest05[bool(visitation_all[i, j])] += 1
                if 5. - delta < dist_to_origin < 5. + delta:
                    radius_5[bool(visitation_all[i, j])] += 1
        with logger.tabular_prefix(prefix):
            logger.record_tabular('r_furthest075', radius_furthest075[True]/radius_furthest075[False])
            logger.record_tabular('r_furthest05', radius_furthest05[True]/radius_furthest05[False])
            logger.record_tabular('r_5', radius_5[True]/radius_5[False])
            total_visitation = np.count_nonzero(visitation_all)
            logger.record_tabular('VisitationTotal', total_visitation)
            logger.record_tabular('VisitationOverlap', overlap)

        # now downsample the visitation
        # for down in [5, 10, 20]:
        #     visitation_down = np.zeros(tuple((i//down for i in visitation_all.shape)))
        #     delta_down = delta * down
        #     y_down, x_down = np.mgrid[-furthest:furthest+delta_down:delta_down, -furthest:furthest+delta_down:delta_down]
        #     for i, row in enumerate(visitation_down):
        #         for j, v in enumerate(row):
        #             visitation_down[i, j] = np.sum(visitation_all[down*i:down*(1+i), down*j:down*(j+1)])
        #     plt.figure()
        #     plt.pcolormesh(x_down, y_down, visitation_down, vmax=mesh_density)
        #     plt.title('Visitation_down')
        #     plt.xlim([x_down[0][0], x_down[0][-1]])
        #     plt.ylim([y_down[0][0], y_down[-1][0]])
        #     plt.title('visitation_down{}: {}'.format(down, exp_name))
        #     plt.savefig(osp.join(log_dir, 'visitation_down{}.png'.format(down)))
        #     plt.close()
        #
        #     total_visitation_down = np.count_nonzero(visitation_down)
        #     overlap_down = np.sum(np.where(visitation_down > 1, 1, 0))  # sum of all visitations larger than 1
        #     logger.record_tabular('VisitationTotal_down{}'.format(down), total_visitation_down)
        #     logger.record_tabular('VisitationOverlap_down{}'.format(down), overlap_down)

        plt.cla()
        plt.clf()
        plt.close('all')
        # del fig, ax, cmap, cbar, map_plot
        gc.collect()

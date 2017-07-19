import numpy as np

from rllab.algos.trpo import TRPO
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.envs.mujoco.maze.point_maze_env import PointMazeEnv
from rllab.misc import logger
from rllab.policies.gaussian_mlp_policy import GaussianMLPPolicy
from rllab.sampler.utils import rollout
from sandbox.young_clgan.envs.base import UniformListStateGenerator, FixedStateGenerator
from sandbox.young_clgan.experiments.asym_selfplay.envs.alice_env import AliceEnv
from sandbox.young_clgan.logging import ExperimentLogger


class AsymSelfplayBatch(object):

    def __init__(self, algo_alice, env_alice, start_states, log_dir, num_rollouts=10, start_generation=True):
        self.algo_alice = algo_alice
        self.env_alice = env_alice

        self.num_rollouts = num_rollouts
        self.start_states = start_states
        self.log_dir = log_dir
        self.start_generation = start_generation

    def optimize_batch(self):

        # get paths
        all_alice_paths = []
        self.algo_alice.current_itr = 0
        debug = False

        if not debug:
            with ExperimentLogger(self.log_dir, 'last_alice', snapshot_mode='last', hold_outter_log=True):
                logger.log("Training Alice")

                if self.start_generation:
                    n_starts = len(self.start_states)
                    logger.log("N starts: " + str(n_starts))
                    for i in range(n_starts):
                        self.env_alice.update_start_generator(FixedStateGenerator(self.start_states[i % n_starts]))
                        logger.log("Num itrs: " + str(self.algo_alice.n_itr))
                        alice_paths = self.algo_alice.train()
                        all_alice_paths.extend(alice_paths)
                else:
                    logger.log("Num itrs: " + str(self.algo_alice.n_itr))
                    alice_paths = self.algo_alice.train()
                    all_alice_paths.extend(alice_paths)
        else:
            logger.log("Training Alice")

            if self.start_generation:
                n_starts = len(self.start_states)
                logger.log("N starts: " + str(n_starts))
                for i in range(n_starts):
                    self.env_alice.update_start_generator(FixedStateGenerator(self.start_states[i % n_starts]))
                    logger.log("Num itrs: " + str(self.algo_alice.n_itr))
                    alice_paths = self.algo_alice.train()
                    all_alice_paths.extend(alice_paths)
            else:
                logger.log("Num itrs: " + str(self.algo_alice.n_itr))
                alice_paths = self.algo_alice.train()
                all_alice_paths.extend(alice_paths)

        logger.log("All alice paths: " + str(len(all_alice_paths)))

        new_paths = [path for paths in all_alice_paths for path in paths]
        logger.log("New paths: " + str(len(new_paths)))
        if self.start_generation:
            new_start_states = [self.env_alice._obs2start_transform(path['observations'][-1]) for path in new_paths]
        else:
            new_start_states = [self.env_alice._obs2goal_transform(path['observations'][-1]) for path in new_paths]
        t_alices = [path['rewards'].shape[0] for path in new_paths]
        logger.log("new start states: " + str(len(new_start_states)))

        logger.log("self.num_rollouts: " + str(self.num_rollouts))

        new_start_states = np.array(new_start_states)
        if len(new_start_states) < self.num_rollouts:
            sampled_starts = new_start_states
        else:
            sampled_starts = new_start_states[np.random.choice(np.shape(new_start_states)[0], size=self.num_rollouts)]
            #return np.array(new_start_states[np.random.choice(new_start_states.shape[0], size=self.num_rollouts)])

        return (sampled_starts, t_alices)

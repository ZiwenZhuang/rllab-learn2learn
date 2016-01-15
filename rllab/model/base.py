from rllab.misc import autoargs
from rllab.core.parameterized import Parameterized


class Model(Parameterized):

    def __init__(self, mdp):
        self._observation_shape = mdp.observation_shape
        self._observation_dtype = mdp.observation_dtype
        self._action_dim = mdp.action_dim
        self._action_dtype = mdp.action_dtype

    def predict_obs_sym(self, obs_var, action_var, train=False):
        raise NotImplementedError

    def predict_reward_sym(self, obs_var, action_var, train=False):
        raise NotImplementedError

    def obs_regression_obj(self, obs_var, action_var, next_obs_var,
                           train=False):
        raise NotImplementedError

    def reward_regression_obj(self, obs_var, action_var, reward_var,
                              train=False):
        raise NotImplementedError

    @classmethod
    @autoargs.add_args
    def add_args(cls, parser):
        pass

    @classmethod
    @autoargs.new_from_args
    def new_from_args(cls, args, mdp):
        pass

    @property
    def observation_shape(self):
        return self._observation_shape

    @property
    def observation_dtype(self):
        return self._observation_dtype

    @property
    def action_dim(self):
        return self._action_dim

    @property
    def action_dtype(self):
        return self._action_dtype

    def log_extra(self, logger, paths):
        """
        Log extra information per iteration based on the collected paths
        """
        pass
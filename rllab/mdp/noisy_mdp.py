import numpy as np
from rllab.core.serializable import Serializable
from rllab.mdp.proxy_mdp import ProxyMDP
from rllab.misc import autoargs
from rllab.misc.overrides import overrides


class NoisyObservationMDP(ProxyMDP, Serializable):

    @autoargs.arg('obs_noise', type=float,
                  help='Noise added to the observations (note: this makes the '
                       'problem non-Markovian!)')
    def __init__(self,
                 mdp,
                 obs_noise=1e-1,
                 ):
        super(NoisyObservationMDP, self).__init__(mdp)
        Serializable.quick_init(self, locals())
        self.obs_noise = obs_noise

    def get_obs_noise_scale_factor(self, obs):
        # return np.abs(obs)
        return np.ones_like(obs)

    def inject_obs_noise(self, obs):
        """
        Inject entry-wise noise to the observation. This should not change
        the dimension of the observation.
        """
        noise = self.get_obs_noise_scale_factor(obs) * self.obs_noise * \
            np.random.normal(size=obs.shape)
        return obs + noise

    def get_current_obs(self):
        return self.inject_obs_noise(self._mdp.get_current_obs())

    @overrides
    def reset(self):
        obs = self._mdp.reset()
        return self.inject_obs_noise(obs)

    @overrides
    def step(self, action):
        next_obs, reward, done = self._mdp.step(action)
        return self.inject_obs_noise(next_obs), reward, done


class DelayedActionMDP(ProxyMDP, Serializable):

    @autoargs.arg('action_delay', type=int,
                  help='Time steps before action is realized')
    def __init__(self,
                 mdp,
                 action_delay=3,
                 ):
        assert action_delay > 0, "Should not use this mdp transformer"
        super(DelayedActionMDP, self).__init__(mdp)
        Serializable.quick_init(self, locals())
        self.action_delay = action_delay
        self._queued_actions = None

    @overrides
    def reset(self):
        self._mdp.reset()
        self._queued_actions = np.zeros(self.action_delay * self.action_dim)
        return self.get_current_obs()

    @overrides
    def step(self, action):
        # original_state = self.delayed_state[:self.original_state_len]
        # queued_action = state[self.original_state_len:][:self.action_dim]
        # import pdb; pdb.set_trace()
        queued_action = self._queued_actions[:self.action_dim]
        next_obs, reward, done = self._mdp.step(queued_action)
        self._queued_actions = np.concatenate([
            self._queued_actions[self.action_dim:],
            action
        ])
        return next_obs, reward, done

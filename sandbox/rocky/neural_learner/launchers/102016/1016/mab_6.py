from rllab.misc.instrument import run_experiment_lite
from rllab import config
from rllab.misc.instrument import VariantGenerator, variant
from sandbox.rocky.cirrascale.launch_job import launch_cirrascale
import numpy as np

from sandbox.rocky.neural_learner.envs.mab_env import MABEnv
from sandbox.rocky.neural_learner.envs.multi_env import MultiEnv

"""
Test using larger networks
"""

USE_GPU = True
USE_CIRRASCALE = False
MODE = launch_cirrascale("pascal")


class VG(VariantGenerator):

    @variant
    def seed(self):
        return [11, 21, 31]

    @variant
    def batch_size(self):
        if MODE == "local":
            return [10000]
        return [250000]

    @variant
    def docker_image(self):
        return [
            # "dementrock/rllab3-shared",
            "dementrock/rllab3-vizdoom-gpu-cuda80"
        ]

    @variant
    def clip_lr(self):
        yield 0.3

    @variant
    def use_kl_penalty(self):
        return [False]

    @variant
    def nonlinearity(self):
        return ["relu"]

    @variant
    def n_arms(self):
        return [10, 50]

    @variant
    def mean_kl(self):
        yield 0.01

    @variant
    def layer_normalization(self):
        return [False]

    @variant
    def n_episodes(self):
        return [500]

    @variant
    def weight_normalization(self):
        return [True]

    @variant
    def min_epochs(self):
        yield 10

    @variant
    def opt_batch_size(self):
        yield 128

    @variant
    def opt_n_steps(self):
        return [None]

    @variant
    def batch_normalization(self):
        return [False]

    @variant
    def entropy_bonus_coeff(self):
        yield 0.001

    @variant
    def discount(self):
        yield 0.99

    @variant
    def gae_lambda(self):
        yield 0.995

    @variant
    def hidden_dim(self):
        return [32, 64, 128, 256, 512]


vg = VG()

variants = vg.variants()

print("#Experiments: %d" % len(variants))

for vv in variants:

    def run_task(v):
        from sandbox.rocky.neural_learner.baselines.l2_rnn_baseline import L2RNNBaseline
        from sandbox.rocky.neural_learner.algos.pposgd_clip_ratio import PPOSGD
        from sandbox.rocky.neural_learner.optimizers.tbptt_optimizer import TBPTTOptimizer
        from sandbox.rocky.neural_learner.policies.categorical_rnn_policy import CategoricalRNNPolicy
        from sandbox.rocky.tf.envs.base import TfEnv
        import tensorflow as tf
        from sandbox.rocky.tf.policies.rnn_utils import NetworkType

        env = TfEnv(MultiEnv(wrapped_env=MABEnv(n_arms=v["n_arms"]), n_episodes=v["n_episodes"], episode_horizon=1,
                             discount=v["discount"]))

        baseline = L2RNNBaseline(
            name="vf",
            env_spec=env.spec,
            log_loss_before=False,
            log_loss_after=False,
            hidden_nonlinearity=getattr(tf.nn, v["nonlinearity"]),
            weight_normalization=v["weight_normalization"],
            layer_normalization=v["layer_normalization"],
            state_include_action=False,
            optimizer=TBPTTOptimizer(
                batch_size=v["opt_batch_size"],
                n_steps=v["opt_n_steps"],
                n_epochs=v["min_epochs"],
            ),
            batch_size=v["opt_batch_size"],
            n_steps=v["opt_n_steps"],
            hidden_dim=v["hidden_dim"],
        )

        policy = CategoricalRNNPolicy(
            env_spec=env.spec,
            hidden_nonlinearity=getattr(tf.nn, v["nonlinearity"]),
            weight_normalization=v["weight_normalization"],
            layer_normalization=v["layer_normalization"],
            network_type=NetworkType.GRU,
            # state_include_action=True,
            name="policy",
            hidden_dim=v["hidden_dim"],
        )

        algo = PPOSGD(
            env=env,
            policy=policy,
            baseline=baseline,
            batch_size=v["batch_size"],
            max_path_length=v["n_episodes"],
            sampler_args=dict(n_envs=max(1, int(np.ceil(v["batch_size"] / v["n_episodes"])))),
            n_itr=500,
            step_size=v["mean_kl"],
            clip_lr=v["clip_lr"],
            log_loss_kl_before=False,
            log_loss_kl_after=False,
            use_kl_penalty=v["use_kl_penalty"],
            min_n_epochs=v["min_epochs"],
            entropy_bonus_coeff=v["entropy_bonus_coeff"],
            optimizer=TBPTTOptimizer(
                batch_size=v["opt_batch_size"],
                n_steps=v["opt_n_steps"],
                n_epochs=v["min_epochs"],
            ),
            discount=v["discount"],
            gae_lambda=v["gae_lambda"],
            use_line_search=True
        )
        algo.train()


    config.DOCKER_IMAGE = vv["docker_image"]  #
    config.KUBE_DEFAULT_NODE_SELECTOR = {
        "aws/type": "c4.8xlarge",
    }
    config.KUBE_DEFAULT_RESOURCES = {
        "requests": {
            "cpu": 36 * 0.75,
            "memory": "50Gi",
        },
    }
    config.AWS_INSTANCE_TYPE = "c4.2xlarge"
    config.AWS_SPOT = True
    config.AWS_SPOT_PRICE = '1.0'
    config.AWS_REGION_NAME = 'us-west-2'
    config.AWS_KEY_NAME = config.ALL_REGION_AWS_KEY_NAMES[config.AWS_REGION_NAME]
    config.AWS_IMAGE_ID = config.ALL_REGION_AWS_IMAGE_IDS[config.AWS_REGION_NAME]
    config.AWS_SECURITY_GROUP_IDS = config.ALL_REGION_AWS_SECURITY_GROUP_IDS[config.AWS_REGION_NAME]

    if MODE == "local_docker":
        env = dict(CUDA_VISIBLE_DEVICES="3")
    else:
        env = dict()

    run_experiment_lite(
        run_task,
        exp_prefix="mab-6",
        mode=MODE,
        n_parallel=0,
        seed=vv["seed"],
        use_gpu=USE_GPU,
        use_cloudpickle=True,
        variant=vv,
        snapshot_mode="last",
        env=env,
        terminate_machine=True,
        sync_all_data_node_to_s3=False,
    )
    # sys.exit()
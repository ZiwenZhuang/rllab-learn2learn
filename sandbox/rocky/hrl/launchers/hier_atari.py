from __future__ import print_function
from __future__ import absolute_import

from sandbox.rocky.hrl.policies.stochastic_gru_policy import StochasticGRUPolicy
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from rllab.misc.instrument import stub, run_experiment_lite
from sandbox.rocky.hrl.bonus_evaluators.discrete_bonus_evaluator import DiscreteBonusEvaluator, MODES
from sandbox.rocky.hrl.algos.bonus_algos import BonusTRPO
from sandbox.rocky.hrl.envs.atari import AtariEnv

stub(globals())

from rllab.misc.instrument import VariantGenerator

vg = VariantGenerator()
vg.add("grid_size", [5])  # , 9])
vg.add("batch_size", [50000])  # 1000])#20000])
vg.add("seed", [11, 111, 211, 311, 411])
vg.add("bonus_coeff", [0.])#, 0.001, 0.1, 0.01, 1.0, 10.0])
vg.add("bottleneck_coeff", [0.])#, 0.001, 0.1, 0.01, 1.0, 10.0])
vg.add("use_trust_region", [False])
vg.add("step_size", [0.])
vg.add("use_decision_nodes", [False])
vg.add("use_bottleneck", [True])
vg.add("deterministic_bottleneck", [True])
vg.add("random_reset", [False])
vg.add("hidden_sizes", [(32, 32)])#, (64, 64), (128, 128), (256, 256), (64, 64, 64), (128, 128, 128), (256, 256, 256)])
vg.add("bottleneck_dim", [10, 20, 30, 40])
vg.add("use_exact_regressor", [True])#True, False])
vg.add("exact_entropy", [False])#lambda use_exact_regressor: [True, False] if use_exact_regressor else [False])
vg.add("mode", [
    # MODES.MODE_MARGINAL_PARSIMONY,
    # MODES.MODE_JOINT_MI_PARSIMONY,
    # MODES.MODE_MI_FEUDAL_SYNC,
    # MODES.MODE_MI_FEUDAL,
    # MODES.MODE_HIDDEN_AWARE_PARSIMONY,
    MODES.MODE_BOTTLENECK_ONLY,
])

variants = vg.variants()
print("#Experiments:", len(variants))

for v in variants:
    env = AtariEnv(game="pong", obs_type="ram", frame_skip=4)
    policy = StochasticGRUPolicy(
        env_spec=env.spec,
        n_subgoals=v["grid_size"],
        use_decision_nodes=v["use_decision_nodes"],
        random_reset=v["random_reset"],
        use_bottleneck=v["use_bottleneck"],
        bottleneck_dim=v["bottleneck_dim"],
        deterministic_bottleneck=v["deterministic_bottleneck"],
        hidden_sizes=v["hidden_sizes"],
    )
    baseline = LinearFeatureBaseline(env_spec=env.spec)
    bonus_evaluator = DiscreteBonusEvaluator(
        env_spec=env.spec,
        policy=policy,
        mode=v["mode"],
        bonus_coeff=v["bonus_coeff"],
        bottleneck_coeff=v["bottleneck_coeff"],
        regressor_args=dict(
            use_trust_region=v["use_trust_region"],
            step_size=v["step_size"],
        ),
        use_exact_regressor=v["use_exact_regressor"],
        exact_entropy=v["exact_entropy"],
    )
    algo = BonusTRPO(
        env=env,
        policy=policy,
        baseline=baseline,
        batch_size=v["batch_size"],
        bonus_evaluator=bonus_evaluator,
        step_size=0.01,
        max_path_length=4500,
        n_itr=500,
    )

    run_experiment_lite(
        algo.train(),
        exp_prefix="hrl_atari_vary_bottleneck",
        n_parallel=2,
        seed=v["seed"],
        mode="lab_kube",
    )
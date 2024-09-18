# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "arviz",
#     "marimo",
#     "xarray",
#     "matplotlib",
#     "scipy",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.8.15"
app = marimo.App(width="medium")


@app.cell
def __(az):
    _data = az.load_arviz_data('centered_eight')
    az.plot_autocorr(_data)
    # [az.plot_autocorr(_data), 
    # type(az.plot_autocorr(_data))]
    return


@app.cell
def __(az, np):
    _idata = az.from_dict(posterior={"a":np.random.normal(1, 0.5, 5000)},
        prior={"a":np.random.normal(0, 1, 5000)})
    az.plot_bf(_idata, var_name="a", ref_val=0)
    # [az.plot_bf(_idata, var_name="a", ref_val=0),
    # type(az.plot_bf(_idata, var_name="a", ref_val=0))]
    return


@app.cell
def __(az, np):
    _data = az.load_arviz_data("regression1d")
    # [az.plot_bpv(_data, kind="t_stat", t_stat=lambda x:np.percentile(x, q=50, axis=-1)), type(az.plot_bpv(_data, kind="t_stat", t_stat=lambda x:np.percentile(x, q=50, axis=-1)))]
    az.plot_bpv(_data, kind="t_stat", t_stat=lambda x:np.percentile(x, q=50, axis=-1))
    return


@app.cell
def __(az):
    _model_compare = az.compare({'Centered 8 schools': az.load_arviz_data('centered_eight'),
                     'Non-centered 8 schools': az.load_arviz_data('non_centered_eight')})
    # [az.plot_compare(_model_compare), type(az.plot_compare(_model_compare))]
    az.plot_compare(_model_compare)
    return


@app.cell
def __(az):
    _centered = az.load_arviz_data('centered_eight')
    _non_centered = az.load_arviz_data('non_centered_eight')
    # [az.plot_density([_centered, _non_centered]), type(az.plot_density([_centered, _non_centered]))]
    az.plot_density([_centered, _non_centered])
    return


@app.cell
def __():
    # az.clear_data_home()
    # _data = az.load_arviz_data('rugby')
    # [az.plot_dist_comparison(_data, var_names=["defs"], coords={"team" : ["Italy"]}), type(az.plot_dist_comparison(_data, var_names=["defs"], coords={"team" : ["Italy"]}))]
    return


@app.cell
def __(az, np):
    _values = np.random.normal(0, 1, 500)
    # [az.plot_dot(_values), type(az.plot_dot(_values))]
    az.plot_dot(_values)
    return


@app.cell
def __(az, norm, np):
    _sample = norm(0,1).rvs(1000)
    _npoints = 100
    # [az.plot_ecdf(_sample, eval_points=np.linspace(_sample.min(), _sample.max(), _npoints)), type(az.plot_ecdf(_sample, eval_points=np.linspace(_sample.min(), _sample.max(), _npoints)))]
    az.plot_ecdf(_sample, eval_points=np.linspace(_sample.min(), _sample.max(), _npoints))
    return


@app.cell
def __(az):
    _idata1 = az.load_arviz_data("centered_eight")
    _idata2 = az.load_arviz_data("non_centered_eight")
    # [az.plot_elpd(
    #     {"centered model": _idata1, "non centered model": _idata2},
    #     xlabels=True
    # ), type(az.plot_elpd(
    #     {"centered model": _idata1, "non centered model": _idata2},
    #     xlabels=True
    # ))]
    az.plot_elpd(
        {"centered model": _idata1, "non centered model": _idata2},
        xlabels=True
    )
    return


@app.cell
def __(az):
    _data = az.load_arviz_data('centered_eight')
    # [az.plot_energy(_data), type(az.plot_energy(_data))]
    az.plot_energy(_data)
    return


@app.cell
def __(az):
    _idata = az.load_arviz_data("centered_eight")
    _coords = {"school": ["Choate", "Lawrenceville"]}
    az.plot_ess(
        _idata, kind="local", var_names=["mu", "theta"], coords=_coords
    )
    # [az.plot_ess(
    #     _idata, kind="local", var_names=["mu", "theta"], coords=_coords
    # ), type(az.plot_ess(
    #     _idata, kind="local", var_names=["mu", "theta"], coords=_coords
    # ))]
    return


@app.cell
def __(az):
    _non_centered_data = az.load_arviz_data('non_centered_eight')
    _axes = az.plot_forest(_non_centered_data,
                               kind='forestplot',
                               var_names=["^the"],
                               filter_vars="regex",
                               combined=True,
                               figsize=(9, 7))
    _axes[0].set_title('Estimated theta for 8 schools model')
    # [_axes, type(_axes)]
    return


@app.cell
def __(az, np):
    # time-steps random walk
    _x_data =np.arange(0,100)
    # Mean random walk
    _mu = np.zeros(100)
    for i in _x_data: _mu[i] = _mu[i-1] + np.random.normal(0, 1, 1)
    # Simulated pp samples form the random walk time series
    _y_data = np.random.normal(2 + _mu * 0.5, 0.5, size = (2, 50, 100))
    # [az.plot_hdi(_x_data, _y_data), type(az.plot_hdi(_x_data, _y_data))]
    az.plot_hdi(_x_data, _y_data)
    return i,


@app.cell
def __(az, np):
    _non_centered = az.load_arviz_data('non_centered_eight')
    _mu_posterior = np.concatenate(_non_centered.posterior["mu"].values)
    _tau_posterior = np.concatenate(_non_centered.posterior["tau"].values)
    # [az.plot_kde(_mu_posterior), type(az.plot_kde(_mu_posterior))]
    az.plot_kde(_mu_posterior)
    return


@app.cell
def __(az):
    _radon = az.load_arviz_data("radon")
    _loo_radon = az.loo(_radon, pointwise=True)
    # [az.plot_khat(_loo_radon, show_bins=True), type(az.plot_khat(_loo_radon, show_bins=True))]
    az.plot_khat(_loo_radon, show_bins=True)
    return


@app.cell
def __(az):
    _idata = az.load_arviz_data("radon")
    # [az.plot_loo_pit(idata=_idata, y="y"), type(az.plot_loo_pit(idata=_idata, y="y"))]
    az.plot_loo_pit(idata=_idata, y="y")
    return


@app.cell
def __(az, np, xr):
    _idata = az.load_arviz_data('regression1d')
    _x = xr.DataArray(np.linspace(0, 1, 100))
    _idata.posterior["y_model"] = _idata.posterior["intercept"] + _idata.posterior["slope"]*_x

    # [az.plot_lm(idata=_idata, y="y", x=_x), type(az.plot_lm(idata=_idata, y="y", x=_x))]
    az.plot_lm(idata=_idata, y="y", x=_x)
    return


@app.cell
def __(az):
    _idata = az.load_arviz_data("centered_eight")
    _coords = {"school": ["Deerfield", "Lawrenceville"]}
    # [az.plot_mcse(
    #     _idata, var_names=["mu", "theta"], coords=_coords
    # ), type(az.plot_mcse(
    #     _idata, var_names=["mu", "theta"], coords=_coords
    # ))]
    az.plot_mcse(
        _idata, var_names=["mu", "theta"], coords=_coords
    )
    return


@app.cell
def __(az):
    _centered = az.load_arviz_data('centered_eight')
    _coords = {'school': ['Choate', 'Deerfield']}
    # [az.plot_pair(_centered,
    #             var_names=['theta', 'mu', 'tau'],
    #             kind='kde',
    #             coords=_coords,
    #             divergences=True,
    #             textsize=18), type(az.plot_pair(_centered,
    #             var_names=['theta', 'mu', 'tau'],
    #             kind='kde',
    #             coords=_coords,
    #             divergences=True,
    #             textsize=18))]
    az.plot_pair(_centered,
                var_names=['theta', 'mu', 'tau'],
                kind='kde',
                coords=_coords,
                divergences=True,
                textsize=18)
    return


@app.cell
def __(az):
    _data = az.load_arviz_data('centered_eight')
    # [az.plot_parallel(_data, var_names=["mu", "tau"]), type(az.plot_parallel(_data, var_names=["mu", "tau"]))]
    az.plot_parallel(_data, var_names=["mu", "tau"])
    # plt.show()
    return


@app.cell
def __(az):
    _data = az.load_arviz_data('centered_eight')
    # [az.plot_posterior(_data), type(az.plot_posterior(_data))]
    az.plot_posterior(_data)
    return


@app.cell
def __(az):
    _data = az.load_arviz_data('radon')
    # [az.plot_ppc(_data, data_pairs={"y":"y"}), type(az.plot_ppc(_data, data_pairs={"y":"y"}))]
    az.plot_ppc(_data, data_pairs={"y":"y"})
    # plt.gca()
    return


@app.cell
def __(az, plt):
    _data = az.load_arviz_data('centered_eight')
    # [az.plot_rank(_data), type(az.plot_rank(_data))]
    az.plot_rank(_data)
    plt.gca()
    return


@app.cell
def __(az):
    _idata = az.load_arviz_data('classification10d')
    # [az.plot_separation(idata=_idata, y='outcome', y_hat='outcome', figsize=(8, 1)), type(az.plot_separation(idata=_idata, y='outcome', y_hat='outcome', figsize=(8, 1)))]
    az.plot_separation(idata=_idata, y='outcome', y_hat='outcome', figsize=(8, 1))
    return


@app.cell
def __(az):
    _data = az.load_arviz_data('non_centered_eight')
    _coords = {'school': ['Choate', 'Lawrenceville']}
    # [az.plot_trace(_data, var_names=('theta'), filter_vars="like", coords=_coords), type(az.plot_trace(_data, var_names=('theta'), filter_vars="like", coords=_coords))]
    az.plot_trace(_data, var_names=('theta'), filter_vars="like", coords=_coords)
    return


@app.cell
def __(az, np):
    _nchains, _ndraws = (4, 500)
    _obs_data = {
        "y": 2 * np.arange(1, 9) + 3,
        "z": 2 * np.arange(8, 12) + 3,
    }
    _posterior_predictive = {
        "y": np.random.normal(
            (_obs_data["y"] * 1.2) - 3, size=(_nchains, _ndraws, len(_obs_data["y"]))
        ),
        "z": np.random.normal(
            (_obs_data["z"] * 1.2) - 3, size=(_nchains, _ndraws, len(_obs_data["z"]))
        ),
     }
    _idata = az.from_dict(
        observed_data=_obs_data,
        posterior_predictive=_posterior_predictive,
        _coords={"obs_dim": np.arange(1, 9), "pred_dim": np.arange(8, 12)},
        dims={"y": ["obs_dim"], "z": ["pred_dim"]},
    )
    ax = az.plot_ts(idata=_idata, y="y", y_holdout="z")
    # [ax, type(ax)]
    ax
    return ax,


@app.cell
def __(az):
    _data = az.load_arviz_data('centered_eight')
    az.plot_violin(_data)
    return


@app.cell(hide_code=True)
def __():
    # import libraries
    import marimo as mo
    import numpy as np
    import arviz as az
    import matplotlib.pyplot as plt
    import xarray as xr
    from scipy.stats import uniform, norm
    return az, mo, norm, np, plt, uniform, xr


if __name__ == "__main__":
    app.run()

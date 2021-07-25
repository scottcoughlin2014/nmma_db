import os
import pandas as pd
import numpy as np
from astropy.time import Time

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm
import yaml

from nmma.em.model import (
    SVDLightCurveModel,
    GRBLightCurveModel,
    KilonovaGRBLightCurveModel,
    SupernovaGRBLightCurveModel,
)
from nmma.em.utils import loadEvent, getFilteredMag

matplotlib.rcParams.update(
    {"font.size": 16, "text.usetex": True, "font.family": "Times New Roman"}
)


def load_config(path="./", config_file="config.yaml"):
    """
    Load config and secrets
    """
    with open(os.path.join(path, config_file)) as cyaml:
        config = yaml.load(cyaml, Loader=yaml.FullLoader)

    return config


def get_bestfit_lightcurve(
    model,
    posterior_file,
    svd_path,
    sample_times,
    joint_light_curve=False,
    mag_ncoeff=10,
    lbol_ncoeff=10,
    grb_resolution=10,
    jet_type=0,
):
    """Generates the bestfit lightcurve model
    par model The name of the model used in fitting.
    par posterior_file Location and name of the posterior sample file
    par svd_path Path containing model svd files.
    par sample_times Grid over which the model is evaluated.

    returns 2-tuple (dictionary of bestfit parameters, bestfit model magnitudes)
    """
    # instead of posterior_file, should it be given the candidate
    # name?

    #################
    # Setup the model
    #################
    kilonova_kwargs = dict(
        model=model,
        svd_path=svd_path,
        mag_ncoeff=mag_ncoeff,
        lbol_ncoeff=lbol_ncoeff,
        parameter_conversion=None,
    )
    if joint_light_curve:

        assert model != "TrPi2018", "TrPi2018 is not a kilonova / supernova model"

        if model != "nugent-hyper":

            kilonova_kwargs = dict(
                model=model,
                svd_path=svd_path,
                mag_ncoeff=mag_ncoeff,
                lbol_ncoeff=lbol_ncoeff,
                parameter_conversion=None,
            )

            bestfit_model = KilonovaGRBLightCurveModel(
                sample_times=sample_times,
                kilonova_kwargs=kilonova_kwargs,
                GRB_resolution=grb_resolution,
                jetType=jet_type,
            )

        else:

            bestfit_model = SupernovaGRBLightCurveModel(
                sample_times=sample_times,
                GRB_resolution=grb_resolution,
                jetType=jet_type,
            )

    else:
        if model == "TrPi2018":
            bestfit_model = GRBLightCurveModel(
                sample_times=sample_times, resolution=grb_resolution, jetType=jet_type
            )

        else:
            light_curve_kwargs = dict(
                model=model,
                sample_times=sample_times,
                svd_path=svd_path,
                mag_ncoeff=mag_ncoeff,
                lbol_ncoeff=lbol_ncoeff,
            )
            bestfit_model = SVDLightCurveModel(**light_curve_kwargs)

    ##########################
    # Fetch bestfit parameters
    ##########################
    posterior_samples = pd.read_csv(posterior_file, header=0, delimiter=" ")
    bestfit_idx = np.argmax(posterior_samples.log_likelihood.to_numpy())
    bestfit_params = posterior_samples.to_dict(orient="list")
    for key in bestfit_params.keys():
        bestfit_params[key] = bestfit_params[key][bestfit_idx]

    #########################
    # Generate the lightcurve
    #########################
    _, mag = bestfit_model.generate_lightcurve(sample_times, bestfit_params)
    for filt in mag.keys():
        mag[filt] += 5.0 * np.log10(bestfit_params["luminosity_distance"] * 1e6 / 10.0)
    mag["bestfit_sample_times"] = sample_times
    bestfit_lightcurve_mag = pd.DataFrame.from_dict(mag)

    return posterior_samples, bestfit_params, bestfit_lightcurve_mag


# Parses a file format with a single candidate
def parse_csv(infile):
    # process the numeric data
    in_data = np.genfromtxt(
        infile, dtype=None, delimiter=",", skip_header=1, encoding=None
    )

    # Candidates are given keys that address a 2D array with
    # photometry data
    out_data = []

    for line in in_data[:]:
        # extract time and put in isot format
        time = Time(line[1], format="jd").isot

        filter = line[4]

        magnitude = line[2]

        error = line[3]

        if 99.0 == magnitude:
            magnitude = line[5]
            error = np.inf

        out_data.append([str(time), filter, str(magnitude), str(error)])

    return out_data


def plot_bestfit_lightcurve(
    data_file, bestfit_lightcurve_magKN_KNGRB, error_budget, trigger_time, plotName
):

    data_out = loadEvent(data_file)
    filters = data_out.keys()

    color2 = "coral"

    colors = cm.Spectral(np.linspace(0, 1, len(filters)))[::-1]

    plt.figure(figsize=(20, 28))
    cnt = 0
    for filt, color in zip(filters, colors):
        cnt = cnt + 1
        if cnt == 1:
            ax1 = plt.subplot(len(filters), 1, cnt)
        else:
            ax2 = plt.subplot(len(filters), 1, cnt, sharex=ax1, sharey=ax1)

        if filt not in data_out:
            continue
        samples = data_out[filt]
        t, y, sigma_y = samples[:, 0], samples[:, 1], samples[:, 2]
        t -= trigger_time
        idx = np.where(~np.isnan(y))[0]
        t, y, sigma_y = t[idx], y[idx], sigma_y[idx]
        if len(t) == 0:
            continue

        idx = np.where(np.isfinite(sigma_y))[0]
        plt.errorbar(
            t[idx],
            y[idx],
            sigma_y[idx],
            fmt="o",
            color="k",
            markersize=16,
            label="%s-band" % filt,
        )  # or color=color

        idx = np.where(~np.isfinite(sigma_y))[0]
        plt.errorbar(
            t[idx], y[idx], sigma_y[idx], fmt="v", color="k", markersize=16
        )  # or color=color

        magKN_KNGRB_plot = getFilteredMag(bestfit_lightcurve_magKN_KNGRB, filt)

        plt.plot(
            bestfit_lightcurve_magKN_KNGRB.bestfit_sample_times,
            magKN_KNGRB_plot,
            color=color2,
            linewidth=3,
            linestyle="--",
        )
        plt.fill_between(
            bestfit_lightcurve_magKN_KNGRB.bestfit_sample_times,
            magKN_KNGRB_plot + error_budget,
            magKN_KNGRB_plot - error_budget,
            facecolor=color2,
            alpha=0.2,
        )

        plt.ylabel("%s" % filt, fontsize=48, rotation=0, labelpad=40)

        plt.xlim([0.0, 10.0])
        plt.ylim([26.0, 14.0])
        plt.grid()

        if cnt == 1:
            ax1.set_yticks([26, 22, 18, 14])
            plt.setp(ax1.get_xticklabels(), visible=False)
        elif not cnt == len(filters):
            plt.setp(ax2.get_xticklabels(), visible=False)
        plt.xticks(fontsize=36)
        plt.yticks(fontsize=36)

    # ax1.set_zorder(1)
    plt.xlabel("Time [days]", fontsize=48)
    plt.tight_layout()
    plt.savefig(plotName)
    plt.close()

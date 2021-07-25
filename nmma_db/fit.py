import subprocess
import sys
import os
import json

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm
from astropy.time import Time
import tempfile
import shutil

from nmma.em.model import SVDLightCurveModel, GRBLightCurveModel, KilonovaGRBLightCurveModel, SupernovaGRBLightCurveModel

from nmma_db.utils import get_bestfit_lightcurve, parse_csv, plot_bestfit_lightcurve

def fit_lc(model_name, cand_name, nmma_data, prior_directory='./priors',
           svdmodel_directory='./svdmodels'):

    # Begin with stuff that may eventually replaced with something else,
    # such as command line args or function args.
    
    # Trigger time settings
    # t0 is used as the trigger time if both fit and heuristic are false.
    # Heuristic makes the trigger time 24hours before first detection.
    t0 = 1
    trigger_time_heuristic = False
    fit_trigger_time = True
    
    # Will select prior file if None
    # Can be assigned a filename to be used instead
    prior = None
    
    # Other important settings
    cpus = 2
    nlive = 32
    error_budget = 1.0
    
    ##########################
    # Setup parameters and fit
    ##########################
    
    #label = candname + "_" + model
    label = model_name 
    
    # Set the trigger time
    if fit_trigger_time:
        # Set to earliest detection in preparation for fit
        for line in nmma_data:
            if np.isinf(float(line[3])):
                continue
            else:
                trigger_time = Time(line[0], format='isot').mjd
                break
    elif trigger_time_heuristic:
        # One day before the first non-zero point
        for line in nmma_data:
            if np.isinf(float(line[3])):
                continue
            else:
                trigger_time = Time(line[0], format='isot').mjd - 1
                break
    else:
        # Set the trigger time
        trigger_time = t0
    
    tmin = 0
    tmax = 7
    dt = 0.1
    svd_mag_ncoeff = 10
    svd_lbol_ncoeff = 10
    Ebv_max = 0.5724
    grb_resolution = 7
    jet_type = 0
    joint_light_curve = False
    sampler = 'pymultinest'
    seed = 42
    
    # Set the prior file. Depends on model and if trigger time is a parameter.
    if prior == None:
        if joint_light_curve:
            if model_name != 'nugent-hyper':
                #KN+GRB
                print("Not yet configured for KN+GRB")
                quit()
            else:
                #supernova
                print("Not yet configured for Supernova")
                quit()
        else:
            if model_name == 'TrPi2018':
                # GRB
                if fit_trigger_time:
                    prior = f'{prior_directory}/ZTF_grb_t0.prior'
                else:
                    prior = f'{prior_directory}/ZTF_grb.prior'
            else:
                # KN
                if fit_trigger_time:
                    prior = f'{prior_directory}/ZTF_kn_t0.prior'
                else:
                    prior = f'{prior_directory}/ZTF_kn.prior'
    
    plotdir = tempfile.mkdtemp()

    # output the data
    # in the format desired by NMMA
    with tempfile.NamedTemporaryFile(suffix='.dat', mode='w') as outfile:
        for line in nmma_data:
            outfile.write(line[0] + " " + line[1] + " " + line[2] + " " + line[3] + "\n")

        # NMMA lightcurve fitting
        # triggered with a shell command
        command = subprocess.run("light_curve_analysis"\
            + " --model " + model_name + " --svd-path " + svdmodel_directory + " --outdir " + plotdir\
            + " --label " + cand_name + "_" + model_name + " --trigger-time " + str(trigger_time)\
            + " --data " + outfile.name + " --prior " + prior + " --tmin " + str(tmin)\
            + " --tmax " + str(tmax) + " --dt " + str(dt) + " --error-budget " + str(error_budget)\
            + " --nlive " + str(nlive) + " --Ebv-max " + str(Ebv_max), shell=True, capture_output=True)
        sys.stdout.buffer.write(command.stdout)
        sys.stderr.buffer.write(command.stderr)
        
        ##############################
        # Construct the best fit model
        ##############################
        
        plot_sample_times_KN = np.arange(0., 30., 0.1)
        plot_sample_times_GRB = np.arange(30., 950., 1.)
        plot_sample_times = np.concatenate((plot_sample_times_KN, plot_sample_times_GRB))
        posterior_file = os.path.join(plotdir, cand_name + '_' + model_name + '_posterior_samples.dat')
        json_file = os.path.join(plotdir, cand_name + '_' + model_name + '_result.json')
        
        with open(json_file, 'r') as f:
            lcDict = json.load(f)

        log_bayes_factor = lcDict["log_bayes_factor"]
        log_evidence = lcDict["log_evidence"]
        log_evidence_err = lcDict["log_evidence_err"]

        posterior_samples, bestfit_params, bestfit_lightcurve_magKN_KNGRB = get_bestfit_lightcurve(model_name, posterior_file, svdmodel_directory, plot_sample_times)
        
        #if fit_trigger_time:
        #    trigger_time += bestfit_params['KNtimeshift']

        plotName = os.path.join(plotdir, 'lightcurves.png')
        plot_bestfit_lightcurve(outfile.name, bestfit_lightcurve_magKN_KNGRB,
                                error_budget, plotName)        

    shutil.rmtree(plotdir)

    return posterior_samples, bestfit_params, bestfit_lightcurve_magKN_KNGRB, log_bayes_factor

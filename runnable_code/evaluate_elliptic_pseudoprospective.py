import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm
from scipy.stats import ttest_rel
import datetime as dt
import math
import sys

from etas.mc_b_est import round_half_up
from etas.inversion import triggering_kernel, parameter_dict2array, to_days, haversine, hav, expected_aftershocks, expected_aftershocks_free_prod, haversine_elliptic

run_number = int(sys.argv[1]) - 1
#block = 5
block = 4500
slopes = [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 1, 2, 3, 4]
#slopes = [0,1,2,3,4]
slope = slopes[run_number]

run_number=0

start=dt.datetime(1980,1,1)

sources = pd.read_csv(f"../etas/output_data/sources_europe_cut_region_ellipse_oldcat_nodup.csv")

cat=pd.read_csv("emsc_merged_cat_2018.csv",index_col=0)#.query("time>=@start")
cat.magnitude = round_half_up(cat.magnitude * 5) // 5
times=[]
for x in cat["time"]:
    try:
        times.append(dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"))
    except:
        times.append(dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f"))
cat["time"] = times
cat.sort_values("time", inplace=True)

sources_0 = pd.read_csv(f"../etas/output_data/sources_europe_cut_region_fixed.csv")
sources_index_0=sources_0.source_id

cat2 = cat.query("time>=@start").copy()
start2 = dt.datetime(2015,1,1)
test_cat = cat.query("time>=@start2").copy()

# test_cat=pd.read_csv("emsc_2015_2018_filtered.csv",index_col=0)
# times=[]
# for x in test_cat["time"]:
#     try:
#         times.append(dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S"))
#     except:
#         times.append(dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f"))
# test_cat["time"] = times
# test_cat.sort_values("time", inplace=True)


#test_cat.query("magnitude>=4.5", inplace=True)
#test_cat=pd.read_csv("two_year_cont.csv",parse_dates=["time"],index_col=0)
# cat2 = pd.concat([cat2,test_cat]).reset_index().drop(columns="index")

#fillna with 1
#cat2["aspect_ratio"] = cat2.aspect_ratio.fillna(1)
#cat2["orientation"] = cat2.orientation.fillna(1)
folder_name = "ellipses_evaluation_output/pseudoprospective/"

mc = 3.5

theta_ellipse = {
    'a': 2.200463473795427,
    'gamma': 1.415898617123485,
    'log10_c': -2.6019384720803362,
    'log10_d': 0.8331798021862536,
    'log10_iota': None,
    'log10_k0': -1.606744850995688,
    'log10_mu': -7.83721772631417,
    'log10_tau': 3.6370349732014136,
    'omega': -0.09788518589288804,
    'rho': 0.6981330484664455
}

theta_circle = {
    'a': 1.7606466952717013,
    'gamma': 0.9450989242416782,
    'log10_c': -2.5575733305094994,
    'log10_d': 0.8955179144121055,
    'log10_iota': None,
    'log10_k0': -1.6035703842600924,
    'log10_mu': -7.425171307747565,
    'log10_tau': 3.6675927662512797,
    'omega': -0.08985726787398414,
    'rho': 0.6665150303205001
}


params = parameter_dict2array(theta_circle), mc
params2 = parameter_dict2array(theta_circle)[2:], mc
params3 = parameter_dict2array(theta_circle)[4:], mc
params_e = parameter_dict2array(theta_ellipse), mc
params2_e = parameter_dict2array(theta_ellipse)[2:], mc
params3_e = parameter_dict2array(theta_ellipse)[4:], mc
area = 15914962.29

k = 0
rates_circle = []
rates_ellipse = []
scores_circle = []
scores_ellipse = []

ar_max = 100
#cat2.loc[cat2['aspect_ratio'] > ar_max, 'aspect_ratio'] = ar_max
#cat2['orientation'] = np.ones(len(cat2))
#run_number+=1
#cat2.loc[cat2['magnitude'] < mag_threshold, 'aspect_ratio'] = 1
#cat2.loc[cat2['aspect_ratio'] > 1, 'orientation'] = cat2.loc[cat2['aspect_ratio'] > 1, 'orientation'] + or_error * np.pi / 180

# for i, event in tqdm(triggered.iterrows(), total=len(triggered)):
for i in tqdm(np.arange(len(test_cat))):
    event = test_cat.iloc[i]
    t_i = event["time"]
    if k < (block * run_number):
        k += 1
        continue
    if k >= block * (run_number + 1): break

    n_events = int(np.floor(i / 5) * 5)
    if n_events == 0:
        sources = pd.read_csv(f"sources_europe_cut_region_after_{3550}_new_events_step5_dynamic_ar.csv")
    else:
        sources = pd.read_csv(f"sources_europe_cut_region_after_{n_events}_new_events_step5_dynamic_ar_test_slope_{slope}.csv")
    print(len(sources))

    cat2 = cat.merge(sources, "left",left_on=cat.index,right_on="source_id")[["time",
                                                                            "longitude",
                                                                            "latitude",
                                                                            "magnitude",
                                                                            "mc_current",
                                                                            "aspect_ratio",
                                                                            "orientation",
                                                                            "G",
                                                                            "l_hat"
                                                                            ]].copy().sort_values("time")
    cat2.loc[cat2['aspect_ratio'] > ar_max, 'aspect_ratio'] = ar_max
    cat2["aspect_ratio"] = cat2.aspect_ratio.fillna(1)
    cat2["orientation"] = cat2.orientation.fillna(1)
    cat2["l_hat"] = cat2.l_hat.fillna(0)
    print(len(cat2))

    previous_events = cat2.query("time < @t_i").copy()
    print(len(previous_events))
    #previous_events_0 = cat3.query("time < @t_i").copy()
    time_distance = to_days(event.time - previous_events.time)
    time_d = to_days(event.time - previous_events.iloc[-1].time)
    to_start = to_days(previous_events.iloc[-1].time - previous_events.time)
    #print(time_d)
    m = previous_events.magnitude
    spatial_distance_squared = np.square(
                haversine_elliptic(
                    np.radians(event.latitude),
                    np.radians(previous_events.latitude),
                    np.radians(event.longitude),
                    np.radians(previous_events.longitude),
                    np.ones(len(previous_events)), np.ones(len(previous_events))
                )
            )
    spatial_distance_squared_e = np.square(
                haversine_elliptic(
                    np.radians(event.latitude),
                    np.radians(previous_events.latitude),
                    np.radians(event.longitude),
                    np.radians(previous_events.longitude),
                    #np.ones(len(previous_events)), np.ones(len(previous_events))
                    previous_events.aspect_ratio, previous_events.orientation
                )
            )
    metrics = time_distance, spatial_distance_squared, m, None
    metrics_e = time_distance, spatial_distance_squared_e, m, None
    
    rate_at_current = triggering_kernel(metrics, params_e)
    rate_at_current_elliptic = triggering_kernel(metrics_e, params_e)

    integral = expected_aftershocks((m, to_start, time_distance), params2_e).sum() + np.power(10,params_e[0][0]) * area * time_d
    integral_e = expected_aftershocks((m, to_start, time_distance), params2_e).sum() + np.power(10,params_e[0][0]) * area * time_d
    # integral = expected_aftershocks_free_prod((m, productivity_0, to_start, time_distance), params3).sum() + np.power(10,params[0][0]) * area * time_d
    # integral_e = expected_aftershocks_free_prod((m, productivity_e, to_start, time_distance), params3_e).sum() + np.power(10,params_e[0][0]) * area * time_d
    
    scores_circle.append(np.log(np.sum(rate_at_current) + np.power(10, params_e[0][0])) - integral)
    scores_ellipse.append(np.log(np.sum(rate_at_current_elliptic) + np.power(10, params_e[0][0])) - integral_e)
    k += 1

# np.save(f"{folder_name}/emsccat_rates_ellipse_new_ardyn_every_5_after_{n_events}.npy", rates_ellipse)
# np.save(f"{folder_name}/emsccat_scores_ellipse_new_ardyn_every_5_after_{n_events}.npy", scores_ellipse)
# np.save(f"{folder_name}/emsccat_rates_etas0_new_every_5_after_{n_events}.npy", rates_circle)
# np.save(f"{folder_name}/emsccat_scores_etas0_new_every_5_after_{n_events}.npy", scores_circle)
    
#np.save(f"{folder_name}/emsccat_2022_rates_ellipse_full.npy", rates_ellipse)
#np.save(f"{folder_name}/emsccat_2022_scores_ellipse_full.npy", scores_ellipse)
#np.save(f"{folder_name}/emsccat_2022_rates_circle_param_only.npy", rates_circle)
#np.save(f"{folder_name}/emsccat_2022_scores_circle_param_only.npy", scores_circle)
    
np.save(f"{folder_name}/emsccat_2018_scores_ellipse_slope_stepf_{slope}.npy", scores_ellipse)
np.save(f"{folder_name}/emsccat_2018_scores_circle_param_only.npy", scores_circle)
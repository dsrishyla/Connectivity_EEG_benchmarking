#!/usr/bin/env python
# coding: utf-8

# In[10]:


import mne
from mne.coreg import Coregistration
from mne.minimum_norm import make_inverse_operator, apply_inverse_epochs
import numpy as np
from pathlib import Path
import pandas as pd
import os
from pathlib import Path
from mne_connectivity import spectral_connectivity_epochs
import xarray as xr
import time


# In[2]:


def filter_labels_with_vertices(labels_parc, src):
    # Get the vertices from both hemispheres in the source space
    src_vertices = [src[0]['vertno'], src[1]['vertno']]
    
    # Initialize an empty list to hold valid labels
    valid_labels = []
    
    for label in labels_parc:
        # Determine the hemisphere index: 0 for 'lh' and 1 for 'rh'
        hemi_idx = 0 if label.hemi == 'lh' else 1
        
        # Check if any of the label's vertices are in the source space for that hemisphere
        if any(v in src_vertices[hemi_idx] for v in label.vertices):
            valid_labels.append(label)
            
    return valid_labels


# In[3]:


subjects = ['sub-032304','sub-032302','sub-032307','sub-032310','sub-032312']
subjects_dir = "/work/erikc/EEG_CON/inspected"
conditions = ['1','2','4','6','8','10','12','14','16','18','20']
conditions2 = ['EC','EO']


# In[4]:


start_time = time.time()


# In[11]:


for subject in subjects:
    conditions_mats = []
    
    src = mne.setup_source_space(subject, add_dist="patch", subjects_dir=subjects_dir)
    conductivity = (0.3, 0.006, 0.3)
    model = mne.make_bem_model(subject=subject, conductivity=conductivity, subjects_dir=subjects_dir)
    bem = mne.make_bem_solution(model)
    labels_parc = mne.read_labels_from_annot(subject, parc='aparc', subjects_dir=subjects_dir)
            
    filtered_labels = filter_labels_with_vertices(labels_parc, src)
            
    
    for condition2 in conditions2:
        raw = mne.io.read_raw_eeglab(f"/work/erikc/EEG_CON/eeg/{subject}/{subject}_{condition2}.set")
        info = raw.info
        fiducials = "estimated"
        coreg = Coregistration(info, subject, subjects_dir, fiducials=fiducials)
        fwd = mne.make_forward_solution(
                raw.info, trans=coreg.trans, src=src, bem=bem, verbose=True
            )
        cov = mne.compute_covariance(raw)
        inv = mne.minimum_norm.make_inverse_operator(raw.info, fwd, cov, verbose=True)
        
        for condition in conditions:
           
            epochs = mne.make_fixed_length_epochs(raw, duration=float(condition), preload=False)
            epochs.set_eeg_reference(projection=True)
            epochs.apply_baseline((None,None))
           
            method = "sLORETA"
            snr = 3.0
            lambda2 = 1.0 / snr**2
            stc = apply_inverse_epochs(
                epochs,
                inv,
                lambda2,
                method=method,
                pick_ori=None,
                verbose=True,
                return_generator=False
            )
            
            label_ts = mne.extract_label_time_course(stc, filtered_labels, src, mode='auto', return_generator=False, allow_empty=False)
            
            n=len(epochs)

            coh_mats=[]
            for i in range(100):
                inds = np.random.choice(range(n),n,replace=True)
                mne_con = spectral_connectivity_epochs(np.array(label_ts)[inds], 
                                                   method="ciplv", sfreq=info['sfreq'], mode='multitaper', 
                                                   fmin=8, fmax=13, fskip=0, faverage=False,
                                                   tmin=None, tmax=None, mt_bandwidth=None, mt_adaptive=False,
                                                   mt_low_bias=True, block_size=1000, n_jobs=1, verbose=None)
                mat = np.real(mne_con.get_data(output="dense"))
                coh_mats.append(mat)

            region = [label.name for label in filtered_labels]
            frequencies = list(mne_con.freqs)
            bootstrap_samples = list(range(100))

            xarray = xr.DataArray(np.array(coh_mats), dims=["bootstrap_samples","region1","region2","frequencies"],
            coords={"bootstrap_samples":bootstrap_samples,"region1":region, "region2":region,"frequencies":frequencies})
            xarray.to_netcdf(f'{subject}_array_ciplv_{condition}_{condition2}.nc')

print(time.time()-start_time)


# In[ ]:





# In[ ]:





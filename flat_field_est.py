import numpy as np
import astropy.io.fits as fits
import astropy.wcs as wcs
import pandas as pd
import scipy.io
from scipy.ndimage import gaussian_filter
import matplotlib
import matplotlib.pyplot as plt
import pickle
from astropy.convolution import convolve
from astropy.convolution import Gaussian2DKernel


def load_flat_from_mat(mat=None, matpath=None, flatidx=6):
	
	if mat is None:
		if matpath is not None:
			mat = loadmat(matpath)
		else:
			return None
		
	flat = mat[0][0][flatidx][0][0][0]
	
	return flat

def compute_ff_mask(joint_masks, ff_stack_min=1):
    
    ff_joint_masks = []
    for j, joint_mask in enumerate(joint_masks):
        
        stack_mask = list(np.array(joint_masks).copy().astype(np.bool))
        
        del(stack_mask[j])
        
        sum_stack_mask = np.sum(stack_mask, axis=0)
        
        ff_joint_mask = (sum_stack_mask > ff_stack_min)
        
        ff_joint_masks.append(ff_joint_mask*joint_mask)
        
    return np.array(ff_joint_masks)


def compute_stack_ff_estimate(images, masks=None, target_image=None, target_mask=None, weights=None, means=None, inv_var_weight=True, nanpct=True, \
							 lopct=5, hipct=95, show_plots=False, infill=True, infill_smooth_scale=3., ff_stack_min=1, ff_min=0.2, field_nfrs=None):
	
	if field_nfrs is None:
		field_nfrs = np.array([1. for x in range(len(images))])


	if masks is not None:
		masked_images = [np.ma.array(images[i], mask=~masks[i]) for i in range(len(images))]
		
		sum_mask = np.sum(np.array(masks), axis=0)

		stack_mask = (sum_mask >= ff_stack_min)

		if show_plots:
			plt.figure()
			plt.imshow(sum_mask)
			plt.colorbar()
			plt.show()
	else:
		masks = [np.full(images[i].shape, True) for i in range(len(images))]
		masked_images = [np.ma.array(images[i], mask=np.full(images[i].shape, False)) for i in range(len(images))]
		
		
	if means is None:
		means = [np.ma.mean(im) for im in masked_images]
	
	print('but means here are ', means)

	if weights is None:
		if inv_var_weight:
			weights = np.array([1./(image_mean*field_nfrs[x]) for x, image_mean in enumerate(means)])
			weights /= np.sum(weights)        
		else:
			weights = np.ones((len(images),))
	
	print('weights are ', weights)
   
	obs_maps = np.array([weights[b]*(images[b]/np.sqrt(np.ma.mean(images[b]))) for b in range(len(weights))])
	print('min max of obs_maps ', np.min(obs_maps), np.max(obs_maps))
	sumim = np.zeros_like(images[0])
	sqrtim = np.zeros_like(images[0])
	
	for i in range(len(images)):
		obssqrt = np.sqrt(np.ma.mean(masked_images[i]))
		sumim += images[i]*masks[i]/obssqrt
		sqrtim += obssqrt*np.ones_like(images[i])*masks[i]
		
	if show_plots:
		plt.figure()
		plt.title('sqrtim')
		if nanpct:
			plt.imshow(sqrtim, vmin=np.nanpercentile(sqrtim, lopct), vmax=np.nanpercentile(sqrtim, hipct))
		else:
			plt.imshow(sqrtim, vmin=np.percentile(sqrtim, lopct), vmax=np.percentile(sqrtim, hipct))
		plt.colorbar()
		plt.show()
		
	sumim /= sqrtim
	
	if infill:
		kernel = Gaussian2DKernel(infill_smooth_scale)
		astropy_conv = convolve(sumim, kernel)

		ff_estimate = sumim.copy()
		ff_estimate[np.isnan(ff_estimate)] = astropy_conv[np.isnan(ff_estimate)]

		if target_mask is not None:
			ff_estimate[target_mask==0] = 1.0

		ff_mask = (ff_estimate != 0)*(ff_estimate > ff_min)

		if masks is not None:
			ff_mask *= stack_mask

		ff_estimate[ff_mask==0] = 1.0

		return ff_estimate, ff_mask, weights

	else:
		return sumim, weights


def plot_indiv_ps_results_fftest(lb, list_of_recovered_cls, cls_truth=None, n_skip_last = 3, mean_labels=None, return_fig=True, ciblab = 'CIB + DGL ground truth', truthlab='truth field average', ylim=[1e-3, 1e2]):
    prefac = lb*(lb+1)/(2*np.pi)
    
    if mean_labels is None:
        mean_labels = [None for x in range(len(list_of_recovered_cls))]
        
    f = plt.figure(figsize=(8,6))
    
    for i, recovered_cls in enumerate(list_of_recovered_cls):
        
        for j in range(recovered_cls.shape[0]):
            
            plt.plot(lb[:-n_skip_last], np.sqrt(prefac*np.abs(recovered_cls[j]))[:-n_skip_last], linewidth=1, marker='.', color='C'+str(i+2), alpha=0.3)
            
        plt.plot(lb[:-n_skip_last], np.sqrt(prefac*np.abs(np.mean(np.abs(recovered_cls), axis=0)))[:-n_skip_last], marker='*', label=mean_labels[i], color='C'+str(i+2), linewidth=3)

    if cls_truth is not None:
        for j in range(cls_truth.shape[0]):
            label = None
            if j==0:
                label = ciblab
            plt.plot(lb[:-n_skip_last], np.sqrt(prefac*cls_truth[j])[:-n_skip_last], color='k', alpha=0.3, linewidth=1, linestyle='dashed', marker='.', label=label)

        plt.plot(lb[:-n_skip_last], np.sqrt(prefac*np.mean(cls_truth, axis=0))[:-n_skip_last], color='k', linewidth=3, label=truthlab)

                
    plt.legend(fontsize=14)
    plt.xscale('log')
    plt.yscale('log')
    plt.ylim(ylim)
    plt.xlabel('Multipole $\\ell$', fontsize=20)
    plt.ylabel('$\\left[\\frac{\\ell(\\ell+1)}{2\\pi}C_{\\ell}\\right]^{1/2}$ [nW m$^{-2}$ sr$^{-1}$]', fontsize=20)
    plt.tick_params(labelsize=16)
    # plt.savefig('/Users/luminatech/Downloads/input_recover_powerspec_fivefields_estimated_ff_bkg250_bl_cut_simidx'+str(simidx)+'_min_stack_ff='+str(min_stack_ff)+'.png', bbox_inches='tight')
    plt.show()
    
    if return_fig:
        return f


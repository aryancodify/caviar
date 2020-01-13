# -*- coding: utf-8 -*-
"""
This module defines some functions aiming at describing subcavities
and caracterize their shapes
"""

import numpy as np
from scipy import ndimage
from skimage.feature import peak_local_max
from skimage.morphology import watershed
from caviar_gui.cavity_identification.gridtools import get_index_of_coor_list
from .cavity import Cavity

__all__ = ['transform_cav2im3d', 'find_subcav_watershed', 'map_subcav_in_cav', 'transform_im3d2cav',
			'transform_cav2im3d_entropy', 'find_subcav_watershed_entropy', 'merge_small_enclosed_subcavs']

def transform_cav2im3d(cavity_coords, grid_min, grid_shape):
	"""
	Takes coordinates of grid points and outputs an im3d for skimage
	could be done in many ways but this one does the job 
	"""
	
	# Simpler version with indices and array reshaping
	#im1d = np.zeros(grid_shape[0]*grid_shape[1]*grid_shape[2])
	#im1d[get_index_of_coor_list(cavity_coords, grid_min, grid_shape)] = 1
	#im3d = np.reshape(im1d, grid_shape)
	# Somehow doesnt' work always


	# Generate an im3d object of correct size for the cavity
	im3d = np.zeros(grid_shape)
	# Align the cavity to zero and convert the silly floats to ints
	aligned_cav = cavity_coords - grid_min
	# np.around because stupid python cant broadcast from floats to ints because floating point error
	# I am lsoing so much time with this kind of stupid behavior, seriously, WTF is this?
	newtypes_cav = np.around(aligned_cav).astype(int)
	# Set as 1 the indices corresponding to cavity grid points in the im3d
	im3d[newtypes_cav[:,0], newtypes_cav[:,1], newtypes_cav[:,2]] = True
	# np.flatnonzero(im3d) should give the same result as
	# get_index_of_coor_list(cavity_coords, grid_min, grid_shape)

	return im3d


def find_subcav_watershed(im3d, seeds_mindist = 3):
	"""
	Uses skimage to perform a watershed algorithm in order to 
	identify subcavities. Seeds of the watershed algorithm are
	defined by maximum local distance to the end of the cavity
	Explanation here: https://scikit-image.org/docs/dev/auto_examples/segmentation/plot_watershed.html
	"""

	# Euclidian distance transform
	distance = ndimage.distance_transform_edt(im3d, sampling=None, return_distances=True,
		return_indices=False, distances=None, indices=None) # Default
	# Find peaks in the image
	# min_distance can be tuned to change the definition of seeds for the watershed algorithm
	# Peaks are separated by at least min_distance
	# increasing the value decreases the number of seeds and thus subpockets
	local_maxi = peak_local_max(distance, min_distance = seeds_mindist, # 
		threshold_abs=None, threshold_rel=None, exclude_border=True, # default
		indices=False, # Modified to return boolean mask
		footprint=None, labels=None,# default
		num_peaks_per_label= 1)#, num_peaks = inf,) # Not several seeds in same label zone
	# label the seeds
	markers = ndimage.label(local_maxi)[0]
	# 
	labels = watershed(-distance, markers = markers, mask=im3d,
		connectivity = 1, offset = None, compactness = 0, watershed_line = False)

	# Labels is of dimension grid_shape and contains integer values corresponding 
	# to the subcavity a point is issued from

	return labels


def transform_cav2im3d_entropy(cavity_coords, grid_min, grid_shape, pharmaco):
	"""
	Takes coordinates of grid points and outputs an im3d for skimage
	Uses entropy at 3A of pharmacophores as values to set the "greyscale"
	"""

	# First we simply the pharmacophores
	names = np.array([0, 1, 1, 3, 3, 3, 4, 5, 0, 0, 0]) # type None & other, hydrophobic, polar, negative, positive
	pharmacophores = names[pharmaco]

	from scipy.spatial import cKDTree
	from scipy.stats import entropy
	
	tree1 = cKDTree(cavity_coords)
	neighbors = tree1.query_ball_point(cavity_coords, r=3)
	list_entropy = []
	for i in neighbors:
		pharma = pharmacophores[:,0][i]
		list_entropy.append(entropy(pharma))

	# Generate an im3d object of correct size for the cavity
	im3d = np.zeros(grid_shape)
	# Align the cavity to zero and convert the silly floats to ints
	aligned_cav = cavity_coords - grid_min
	# np.around because stupid python cant broadcast from floats to ints because floating point error
	# I am lsoing so much time with this kind of stupid behavior, seriously, WTF is this?
	newtypes_cav = np.around(aligned_cav).astype(int)
	# Set as 1 the indices corresponding to cavity grid points in the im3d
	im3d[newtypes_cav[:,0], newtypes_cav[:,1], newtypes_cav[:,2]] = 1/np.array(list_entropy)
	# np.flatnonzero(im3d) should give the same result as
	# get_index_of_coor_list(cavity_coords, grid_min, grid_shape)

	return im3d


def find_subcav_watershed_entropy(im3d, seeds_mindist = 3):
	"""
	Uses skimage to perform a watershed algorithm in order to 
	identify subcavities. Seeds of the watershed algorithm are
	defined by maximum local distance to the end of the cavity
	Explanation here: https://scikit-image.org/docs/dev/auto_examples/segmentation/plot_watershed.html
	"""

	# Euclidian distance transform
	distance = ndimage.distance_transform_edt(im3d, sampling=None, return_distances=True,
		return_indices=False, distances=None, indices=None) + np.round(im3d, 1)
	# Find peaks in the image
	# min_distance can be tuned to change the definition of seeds for the watershed algorithm
	# Peaks are separated by at least min_distance
	# increasing the value decreases the number of seeds and thus subpockets
	local_maxi = peak_local_max(distance, min_distance = seeds_mindist, # 
		threshold_abs=None, threshold_rel=None, exclude_border=True, # default
		indices=False, # Modified to return boolean mask
		footprint=None, labels=None,# default
		num_peaks_per_label= 1)#, num_peaks = inf,) # Not several seeds in same label zone
	# label the seeds
	markers = ndimage.label(local_maxi)[0]
	# 
	labels = watershed(-distance, markers = markers, mask=im3d,
		connectivity = 1, offset = None, compactness = 0, watershed_line = False)

	# Labels is of dimension grid_shape and contains integer values corresponding 
	# to the subcavity a point is issued from

	return labels

def merge_small_enclosed_subcavs(subcavs, minsize_subcavs = 50, min_contacts = 0.667, v = False):
	"""
	The watershed algorithm tends to overspan a bit, even when optimizing seeds.
	This function aims at identifying small pockets (< minsize_subcavs)
	that are heavily in contact with other subcavs (> min_contacts)
	These subcavites are probably at the interface between 2 main subcavities,
	or on their surface.
	"""
	# Create a copy of the subcavs array to not change in place, in case
	_subcavs = np.copy(subcavs)
	# lengths of each subcavity
	lengths = [len(x) for x in subcavs]
	#Smaller ones than min_contacts
	smallsubcavs = [[x, lengths[x]] for x in range(0, len(lengths)) if lengths[x] < minsize_subcavs]
	
	if not smallsubcavs:
		return subcavs
	
	from scipy.spatial.distance import cdist
	
	to_del = {}
	
	for small in smallsubcavs:
		contacts = []
		contact = 0.
		total_contact = 0.
		i = 0
		# Check the contact between the small subcavity and the others
		for other_subcavs in subcavs:
			if i == small[0]:
				contacts.append(0)
				i+=1
				continue
			contact = len(set(np.nonzero(cdist(subcavs[small[0]], other_subcavs) < 1.01)[0]))
			contacts.append(contact)
			total_contact += contact/small[1]
			i+=1
		# If a small subcavity has more than min_contacts with neighbors, be ready to add it to the 
		# subcavity with which it has the more contacts
		if total_contact >= min_contacts:
			if v == True: print(f"Subcavity {small[0]} is small and enclosed {total_contact*100:.2f}% in other subcavs.\nIt will be added to subcavity {np.argmax(contacts)} (original numbering of subcavs from 0)")
			to_del[small[0]] = np.argmax(contacts)
	# If there's any subcavities to merge
	# It's a mess because it's not easy to merge different array elements together and/or delete some...
	if to_del:
		dels = []
		for index in range(0, len(subcavs)):
			if index in to_del.keys():
				_tmp = np.concatenate((_subcavs[to_del[index]], _subcavs[index]), axis = 0)
				_subcavs[to_del[index]] = _tmp
				dels.append(index)
		subcavlist = [x.tolist() for x in _subcavs]
		for _del in sorted(dels, reverse=True):
			del subcavlist[_del]
		merged_subcavs = [np.array(x) for x in subcavlist]
		return merged_subcavs
	else:
		return subcavs


def map_subcav_in_cav(cavities, cav_of_interest, labels, pdbcode, grid_min, grid_shape,
	printv = True, printvv = True):
	"""
	Extract information from subcavities: return the coordinates as subcavs, 
	print information about PP environment
	and in particular, set in cavities object (class) the subcavity indices
	"""

	#names = ["none", "aliphatic", "aromatic", "donor", "acceptor", "doneptor", "negative",
	# "positive", "cys", "his", "metal"]
	# Dictionary of pharmacophore types to print
	names = ["none", "hydrophobic", "shouldnotbethere", "polar non charged", "shouldnotbethere", "shouldnotbethere",
	"negative", "positive", "cys", "his", "metal"]

	subcavs = []
	for i in range(1, np.amax(labels)+1):
		
		subcav = np.argwhere(labels == i) + grid_min
		subcavs.append(subcav)

		# Find the corresponding indices in cavities[cav_of_interest]
		oricav_indices = np.intersect1d(get_index_of_coor_list(subcav, grid_min, grid_shape),
			get_index_of_coor_list(np.array([x.coords for x in cavities[cav_of_interest].gp]), grid_min, grid_shape),
			return_indices=True)[2]
		# Update the cavity object
		cavities[cav_of_interest].subcavities[i-1] = oricav_indices

		if not printv:
			continue
		print(f"subcavity {i+1} of cavity {cav_of_interest+1} of pdb {pdbcode[:-4]} has "
					f"{len(oricav_indices)} grid points")

		if not printvv:
			continue
		# Find the pharmacophore types of the gridpoints of the subcavity
		listouille = [cavities[cav_of_interest].gp[x].pharma[0] for x in oricav_indices]

		# Convert types aromatic into "hydrophobic" alongside aliphatic (original nb1)
		listouille = np.where(np.array(listouille)==2, 1, listouille)
		# Convert types acceptor and doneptor into "polar non charged" (originally donor)
		listouille = np.where(np.array(listouille)==4, 3, listouille)
		listouille = np.where(np.array(listouille)==5, 3, listouille)
	
		# Count occurences of each value
		values, counts = np.unique(listouille, return_counts=True)
		# Get total of values
		total = np.sum(counts)
		for j in range(0, len(values)):
			# Get proportion of this value
			prop = counts[j] / total
			if prop > 0.1: # if more than 10% print info
				print(f"subcavity {i-1} of cavity {cav_of_interest} of pdb {pdbcode[:-4]} has {np.round(prop*100)}"
					f"% of pharmacophores of type {names[values[j]]}")


	return subcavs


def transform_im3d2cav(im3d, grid):
	"""
	Invert of original function. It's a simple command but nice to have it here with a good name
	"""
	cav_coor = grid[np.flatnonzero(im3d)]

	return cav_coor


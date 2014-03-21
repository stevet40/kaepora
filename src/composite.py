"""
Spectra composite program
Authors: Sam, Yixian, Aaron
"""

import matplotlib.pyplot as plt
import numpy as np
import glob
import sqlite3 as sq3
from scipy import interpolate as intp
import math
from astropy.table import Table
import msgpack as msg
import msgpack_numpy as mn
from scipy.optimize import leastsq

np.set_printoptions(threshold=np.nan)
mn.patch()

#Sets up some lists for later
SN_Array = []
full_array = []
compare_spectrum = []
#max_light = []
#max_light = np.loadtxt("../personal/AaronBeaudoin/week4/MaxSpectra.dat", dtype = 'str', delimiter = " ", skiprows = 1)

class supernova(object):
    """Attributes can be added"""
    
class Parameters:
    """Not sure what goes here"""

#Connect to database
#change this address to whereever you locally stored the SNe.db
con = sq3.connect('../../../SNe.db')
#con = sq3.connect('../../temp/SNe.db')
cur = con.cursor()

def grab(sql_input, Full_query):
    print "Collecting data..."
    SN_Array = []
    cur.execute(sql_input)
    #at some point this should be more modular but for now I'm only going to accept the full query
    for row in cur:
        if sql_input == Full_query:
            SN           = supernova()
            SN.filename  = row[0]
            SN.name      = row[1]
	    SN.source    = row[2]
            SN.redshift  = row[3]
	    SN.phase     = row[4]
            SN.minwave   = row[5]
            SN.maxwave   = row[6]
	    SN.dm15      = row[7]
	    SN.m_b       = row[8]
	    SN.B_minus_v = row[9]
	    SN.targeted  = row[10]
	    SN.SNR       = row[11]
            #spectra = msg.unpackb(row[7])
            #SN.spectrum = spectra
	    interp       = msg.unpackb(row[12])
	    SN.interp    = interp
	    try:
		SN.wavelength = SN.interp[0,:]
		SN.flux       = SN.interp[1,:]
		SN.ivar       = SN.interp[2,:]
		
		#print SN.flux
	    except TypeError:
		continue
	    full_array.append(SN)
            SN_Array.append(SN)
            #print SN.interp
	else:
	    print "Invalid query...more support will come"
    print len(SN_Array), "spectra found"

    #cut the array down to be more manageable
    SN_Array = SN_Array[0:100]
    for SN in SN_Array:
	for i in range(len(SN.flux)):
	    if np.isnan(SN.flux[i]):
		SN.flux[i] = 0
	    if np.isnan(SN.ivar[i]):
		SN.ivar[i] = 0
    SN_Array = [SN for SN in SN_Array if hasattr(SN, 'wavelength')]
    SN_Array = [SN for SN in SN_Array if hasattr(SN, 'ivar')]
    print len(SN_Array), "spectra remain"
    return SN_Array


"""
#Only keeps one per supernova at max light. Condition can be changed later.
for SN in full_array:
    for row in max_light:
        if SN.filename in row[1]:
            SN_Array.append(SN)
            SN.age = row[2]
            SN.ages = np.zeros(len(SN.wavelength))
            SN.ages.fill(SN.age)
            #print SN.age
print len(SN_Array)
"""

#gets as close as possible to matching the compare spectrum wavelength values
def find_nearest(array,value):
    idx = (np.abs(array-value)).argmin()
    return array[idx]

def scale_func(vars, in_data, out_data):
    
    scale = vars[0]

    model = scale * in_data
    
#    output = (out_data-model)*ivar**0.5
    output = model
    #needed to reshape this?
    return output[:,0]

def find_scales(SN_Array, temp_flux, temp_ivar):
    min_overlap = 300
    scales = []
    print "Finding scales..."
    #loop over each SN in the array
    for SN in SN_Array:
        #grab out the flux and inverse variance for that SN
        flux = SN.flux
        ivar = SN.ivar
        #Make the combined inverse variance function.  Zeros should multiply to get zeros
        overlap = temp_ivar * ivar
        n_overlap = len([x for x in overlap if x > 0])
	
        if n_overlap < min_overlap:

            #If there is insufficient overlap, the scale is zero.
            scales = np.append(scales, np.array([0]), axis = 0)

        else:
            #Otherwise, fit things
            vars = [1.0]
            #Find the appropriate values for scaling
            good     = np.where(overlap > 0)
	    flux2     = np.array([flux[good]])
	    ivar2     = np.array([ivar[good]])
	    tempflux2 = np.array([temp_flux[good]])
            tempivar2 = np.array([temp_ivar[good]])
            totivar  = 1/(1/ivar2 + 1/tempivar2)

	    result = np.mean(tempflux2/flux2)

	    print "Scale factor = ", result

            scales = np.append(scales, np.array([float(result)]), axis = 0)

    return scales

def scale_data(SN_Array, scales):
    print "Scaling..."
    for i in range(len(scales)):
	SN_Array[i].flux *= np.abs(scales[i])
	SN_Array[i].ivar /= (scales[i])**2  #Check this!!
	print "Scaled at factor ", scales[i]
    return SN_Array

#averages with weights based on the given errors in .flm files
def average(SN_Array, template):
	print "Averaging..."
	#print fluxes, errors
	fluxes = []
	ivars  = []
	for SN in SN_Array:
	    if len(fluxes) == 0:
		fluxes = np.array([SN.flux])
		ivars  = np.array([SN.ivar])
		#waves = np.array([SN.wavelength])
 		#reds = np.array([red])
		#ages = np.array([age])
	    else:
		try:
		    fluxes = np.append(fluxes, np.array([SN.flux]), axis=0)
		    ivars  = np.append(ivars, np.array([SN.ivar]), axis=0)
		    #waves = np.append(waves, np.array([SN.wavelength]), axis=0)
		    #reds = np.append(reds, np.array([red]), axis = 0)
		    #ages = np.append(ages, np.array([age]), axis = 0)
		except ValueError:
		    print "oh god what is happening"
	flux_mask = np.zeros(len(fluxes[0,:]))
	ivar_mask = np.zeros(len(fluxes[0,:]))
	have_data = np.where(np.sum(ivars, axis = 0)>0)
	no_data = np.where(np.sum(ivars, axis = 0)==0)
	ivar_mask[no_data] = 1
	for i in range(len(fluxes)):
	    ivars[i,:] += ivar_mask
        template.flux = np.average(fluxes, weights=ivars, axis=0)
	#template.flux = np.average(fluxes, axis=0)
        template.ivar = 1/np.sum(ivars, axis=0)
	template.ivar[no_data] = 0
	return template

def main():
    SN_Array = []
    #Accept SQL query as input and then grab what we need
    Full_query = "SELECT * FROM Supernovae WHERE Signal_Noise > 8"
    print "SQL Query:", Full_query
    #sql_input = str(raw_input("Enter a SQL Query---> "))
    sql_input = Full_query

    SN_Array = grab(sql_input, Full_query)

    #finds the longest SN we have for comparison
    lengths = []
    for SN in SN_Array:
        lengths.append(len(SN.flux[np.where(SN.flux != 0)]))
    temp = [SN for SN in SN_Array if len(SN.flux[np.where(SN.flux!=0)]) == max(lengths)]
    composite = temp[0]

    #scales data, makes a composite, and splices in non-overlapping data
    wmin = 4000
    wmax = 7500
    wavemin = composite.minwave
    wavemax = composite.maxwave

    #finds range of useable data
    good = np.where(len(np.where(((wavemin <= wmin) & (wavemax >= wmax)) > 100))) #& (SN.SNR>.8*max(SN.SNR)))
    template = supernova()
    template = SN_Array[good[0]]
    template = composite
    
    #Starts our main loop
    i = 0
    n_start = 0
    n_end = 1
    scales=[]
    while (n_start != n_end):
	n_start = len([x for x in scales if x>0])
        scales=[]       
	scales = find_scales(SN_Array, template.flux, template.ivar)
	n_scale = len([x for x in scales if x>0])
	SN_Array = scale_data(SN_Array, scales)
        template = average(SN_Array, template)
        n_end = n_scale
	n_start = n_end
	
	
    print "Done."
    lowindex = np.where(template.wavelength == find_nearest(template.wavelength, wmin))
    highindex = np.where(template.wavelength == find_nearest(template.wavelength, wmax))
    print lowindex[0], highindex[0]
    plt.plot(template.wavelength[lowindex[0]:highindex[0]], template.flux[lowindex[0]:highindex[0]])
    plt.plot(template.wavelength[lowindex[0]:highindex[0]], template.ivar[lowindex[0]:highindex[0]])
    plt.savefig('../plots/TestComposite.png')
    plt.show()
    #Either writes data to file, or returns it to user
    table = Table([template.wavelength, template.flux, template.ivar], names = ('Wavelength', 'Flux', 'Variance'))
    c_file = str(raw_input("Create a file for data? (y/n)"))
    if c_file=='y':
		#f_name='composite,'+min(composite.phases)+'.'+max(composite.phases)+'.'+min(composite.redshifts)+'.'+max(composite.redshifts)+'...--'+np.average(composite.phases)+'.'+np.average(composite.redshifts)+len(SN_Array)+'SN'
		#phase_min.phase_max.deltam15_min.deltam15_max. ... --avg_phase.avg_deltam15... --#SN
		f_name = "../plots/TestComposite"
		table.write(f_name,format='ascii')
    else:
		return table

if __name__ == "__main__":
    main()
This is version 1.04 of the dataset described in Elipot et al. 2016, "A global surface drifter dataset at hourly resolution", JGR-Oceans, doi:10.1002/2016JC011716.  Changes from previous verions are described at http://www.aoml.noaa.gov/phod/gdp/hourly_data.php.

The hourly drifter data are available in Matlab and NetCDF formats.  NetCDF files are provided one per drifter, conforming to the National Centers for Environmental Information (NOAA/NCEI) NetCDF Trajectory Template version 2, and all include metadata such as drogue lost time, drifter manufacturer, deployment information, etc.  The files are available at 
ftp://ftp.aoml.noaa.gov/phod/pub/lumpkin/hourly/netcdf
[CHECK ON THIS ...]

The Matlab files are available as direct links from the hourly drifter data page https://www.aoml.noaa.gov/phod/gdp/hourly_data.php
in nine files, each containing many drifters.  The first eight files, named "hourly_WMLE_[version]_blockN.mat" (N=1-8) contain the Argos-tracked drifters.  Blocks 1-6 have not been updated since version 1.02; block 7 will not be updated past version 1.04, and block 8 will continue to be updated until all Argos drifters are dead.  The last file, "hourly_GPS_[version].mat" contains drifters tracked via GPS.  Each file contains contiguous hourly estimates for the drifters unless the interpolating temporal gap between original positions is greater than 12 hour. In that case, no estimate is provided. When analyzing these data as time series, be aware of temporal time steps that are multiple of 1 hour. Interruptions in contiguous hourly estimates are indicated by "Infinity" values, while separation of individual trajectories is indicated by "NaN" values.

The data in these Matlab files are:
id : identification number from the Global Drifter Program (see deployment log file at http://www.aoml.noaa.gov/phod/dac/deployed.html)
TIME : time in hours since 1 January 1979, such that TIME==318504 corresponds to 3 May 2015 at 0000 UTC.
LON : longitude(degree 0-360)
LAT : latitude (degree North)
LON_ERR : longitude error (10^-5 degree) forming 95% confidence intervals
LAT_ERR : latitude error (10^-5 degree) forming 95% confidence intervals
U : zonal velocity (meter per second)
V : meridional velocity (meter per second)
U_ERR : zonal velocity error (meter per second) forming 95% confidence intervals
V_ERR : meridional velocity error (meter per second) forming 95% confidence intervals
GAP : length of interpolating gap in days; it is the difference between the time of the first Argos fix forward in time minus the time of the last Argos fix backward in time
RMSGAP : root mean square temporal distance in days between the hourly interpolating time and the four Argos fixes used for the estimation (three Argos fixes for beginning and end of trajectory).
DROGUE : drogue status; 1 = drogue on, 0 = drogue off

Questions about the dataset should be addressed to either Rick.Lumpkin@noaa.gov or Shane Elipot at selipot@rsmas.miami.edu

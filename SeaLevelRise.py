##------------------------------------------------------------------------------------------
#       Object Name: SelLevelRise.py
#       Author: Original -- David Ostanski  
#       Description: That is called from a Toolbox script in ArcCatalog
#                    calculating the effects of sealevelrise on a layer
#       Inputs:     Point/Line/Poly Featureclass or shapefile
#       Returns:    Point Featureclass or shapefile
#       Uses: 
#       Date: 7/2008
#       NOTES:
#       History: See sourcesafe
##------------------------------------------------------------------------------------------
"""
usage SeaLevelRise.py <> <>
"""
import sys
import getopt
import arcgisscripting
import traceback
import os
import math
import string
from time import *

def main(argv=None):
    gp = arcgisscripting.create()
    if argv is None:
        argv = sys.argv
    # parse command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.error, msg:
        print msg
        print "for help use --help"
        return 2
    
# process options
    for o, a in opts:
        if o in ("-h", "--help"):
            print __doc__
            return 0
 # process arguments
    process(args, gp)
    return 0

#
#  Creates event table to get a point layer from polyline inputlayer
#  Called by 
#
def mkevents(lfc, wks, evnttblnm, density, mgp):
    mgp.workspace = wks
    if mgp.exists(evnttblnm):
        mgp.Delete_management(evnttblnm)
        
    mgp.CreateTable_management(wks, evnttblnm, "", "")
    mgp.AddField_management(evnttblnm, "routeid", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    mgp.AddField_management(evnttblnm, "eventnumber", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
       
    scur = mgp.searchcursor(lfc)
    icur = mgp.insertcursor(evnttblnm)

    dsc = mgp.describe(lfc)
    oidfn = dsc.OIDFieldname

    readrec = scur.next()
    while readrec:
        measure = 0
        
        if oidfn == 'FID':
            oid = readrec.FID
        else:
            oid = readrec.OBJECTID
            
        if mgp.ListFields(lfc, "Shape_length").next():
            length = readrec.Shape_length
        elif mgp.ListFields(lfc, "Shape_len").next():
            length = readrec.shape_len
        else:
            mgp.adderror("mkevents function: Cannot find length field!")
            mgp.adderror("The length field must be named Shape_length or Shape_len.")
            mgp.adderror("Aborting SeaLevelRise.")            
            sys.exit(0)

        while measure <= length:
            inrec = icur.newrow()
            inrec.routeid = oid
            inrec.eventnumber = measure
            icur.insertrow(inrec)
            measure += density



        readrec = scur.next()
    

def mklineoutput(lfc, owks, density, outlayer, mgp):
    dscOput = mgp.describe(owks)
    tmpLine = 'tmpline'
    evnttblnm = 'tmpeventtab'
    outputtable = "EventTableEvents"
    # if output is a shapefile then 
    # create file geodatabase to create the oplayer
    # else use the output workspace
    if dscOput.WorkspaceType == 'FileSystem':
        fgdbnm = "xxtemp"
        mgp.workspace = owks
        if mgp.exists(fgdbnm + ".gdb"):
            print fgdbnm + ".gdb" + " exists."
            i = 1
            nfgdb = fgdbnm.replace(fgdbnm, fgdbnm + str(i))
            while mgp.exists(nfgdb + ".gdb"):
                i += 1
                nfgdb = nfgdb.replace(nfgdb, fgdbnm + str(i))
            fgdbnm = nfgdb
            
        fgdbnm = fgdbnm + ".gdb"
        print "Creating " + fgdbnm
        mgp.CreateFileGDB_management(owks, fgdbnm)
        fgdb = owks + "\\" + fgdbnm
    else:
        fgdb = owks

    mgp.workspace = fgdb
    if mgp.exists(evnttblnm):
        mgp.Delete_management(evnttblnm)
    if mgp.exists(outputtable):
        mgp.Delete_management(outputtable)
    # call mkevents procedure
    mkevents(lfc, fgdb, evnttblnm, density, mgp)
    
    if mgp.exists(tmpLine):
        mgp.Delete_management(tmpLine)

    # copy input line to tempory fc to get point  
    mgp.FeatureClassToFeatureClass_conversion(lfc, fgdb, tmpLine)
    rtid = "routeid"

    # make sure routeid is not already a field
    # if it already exists, add "_number" to the end 
    if mgp.ListFields(tmpLine, rtid).Next():
        i = 1
        rtid = "routeid_" + str(i)
        while mgp.ListFields(tmpLine, rtid).Next():
            i += 1
            rtid = "routeid_" + str(i)
    # add routeid to temporary line     
    mgp.AddField_management(tmpLine, rtid, "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # calculate routeid field to objectid
    dsc = mgp.describe(tmpLine)
    oidfn = dsc.OIDFieldName
    
    mgp.CalculateField_management(tmpLine, rtid, "[" + str(oidfn) + "]", "VB", "")
    
#    mgp.CalculateField_management(tmpLine, rtid, "[OBJECTID]", "VB", "")

    
    # make sure route layer doesn't exist
    outRoute = "TempRoute"
    if mgp.exists(outRoute):
        mgp.Delete_management(outRoute)
    x = 1
    # run create routes on temp layer    
    mgp.CreateRoutes_lr(tmpLine, rtid, outRoute, "LENGTH", "", "", "UPPER_LEFT", x, "0", "IGNORE", "INDEX")
    mgp.MakeRouteEventLayer_lr(outRoute, rtid, evnttblnm, "routeid POINT eventnumber", outputtable, "", "ERROR_FIELD", "NO_ANGLE_FIELD", "NORMAL", "ANGLE", "LEFT", "POINT")

    # copy event feature layer to output
    mgp.workspace = owks    
    mgp.FeatureClassToFeatureClass_conversion(outputtable, owks, outlayer)

    # cleanup
    if mgp.exists(outRoute):
        mgp.Delete_management(outRoute)
    if mgp.exists(tmpLine):
        mgp.Delete_management(tmpLine)
    if mgp.exists(evnttblnm):
        mgp.Delete_management(evnttblnm)

    if dscOput.WorkspaceType == 'FileSystem':
        mgp.workspace = fgdb
        if mgp.exists(outRoute):
            mgp.Delete_management(outRoute)
        if mgp.exists(tmpLine):
            mgp.Delete_management(tmpLine)
        if mgp.exists(evnttblnm):
            mgp.Delete_management(evnttblnm)

        mgp.workspace = owks
        if mgp.exists(fgdb):
            mgp.Delete_management(fgdbnm)

#
#   create/append to log table
#
#
def writeLogTable(tablename, wks, inrecord, wingp):
    wingp.addwarning("Writing to log table: " + tablename)
    wingp.workspace = wks
    if not wingp.exists(tablename):
        # create table
        wingp.CreateTable_management(wks, tablename)
        wingp.AddField_management(tablename, "FCNAME", "TEXT", "", "", "36", "", "NULLABLE", "NON_REQUIRED", "")
        wingp.AddField_management(tablename, "SRGHT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        wingp.AddField_management(tablename, "TIDEHEIGHT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        wingp.AddField_management(tablename, "SLR", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
                
    # append record
    cur = wingp.InsertCursor(tablename)
    row = cur.NewRow()
    row.FCNAME = inrecord[0]
    row.SRGHT = inrecord[1]
    row.TIDEHEIGHT = inrecord[2]
    row.SLR = inrecord[3]
    cur.InsertRow(row)
    del cur
    del row
    wingp.addwarning("Complete: " + tablename)
    
    
    
#
#   uses a modified list of args to make the layer
# 
#
def createLayer(layerinputs, ngp):
    ngp.addmessage(layerinputs)
    inputFea = layerinputs[0]
    pointDensity = layerinputs[1]
    elevField = layerinputs[2]
    threeDTin = layerinputs[3]
    threeDRaster = layerinputs[4]
    surgeHeight = layerinputs[7]
    currentTides = layerinputs[5]
    slrHeight = layerinputs[6]
    outputwks = layerinputs[9] 
    outputtype = layerinputs[10]
    oplayer = layerinputs[11]
    shpType = layerinputs[12]
    linearunit = layerinputs[13]
    threeDLayer = '#'
    print '----- LayerInputs -----'
    print layerinputs
    
    #
    # if there is an elevation field, create output point featureclass
    #   else setup for 
    if elevField <> '#':
        ngp.addwarning('Elevation field: ' + elevField)
        #
        #   create outputlayer depending on shapetype
        #
        if shpType == 'Point':
            # copy source point to oplayer and use oplayer
            ngp.FeatureClassToFeatureClass_conversion(inputFea, outputwks, oplayer)
        elif shpType == 'Polyline':
            # create oplayer
            ngp.addWarning("Processing polyline...")
            mklineoutput(inputFea, outputwks, pointDensity, oplayer, ngp)
        elif shpType == 'Polygon':
            #
            #   test to see if density field exists:  Add density field, then calc it
            #
            densityfld = "xdensity"
            if ngp.ListFields(inputFea, densityfld).Next():
                i = 1
                rtid = "xdensity_" + str(i)
                while ngp.ListFields(inputFea, densityfld).Next():
                    i += 1
                    densityfld = "xdensity_" + str(i)
            # add routeid to temporary line   
            ngp.AddField_management(inputFea, densityfld, "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            ngp.CalculateField_management(inputFea, densityfld, "[SHAPE_Area] / " + str(pointDensity), "VB","") 
            
            ngp.CreateRandomPoints_management(outputwks, oplayer, inputFea, "0 0 250 250", str(densityfld))

            if ngp.ListFields(inputFea, densityfld).Next():
                ngp.DeleteField(inputFea, densityfld)
                
                
            ngp.addWarning("Processing polygon...")
    elif elevField == '#' and threeDTin <> '#':
        threeDLayer = threeDTin
    elif elevField == '#' and threeDTin == '#' and threeDRaster <> '#':
        threeDLayer = threeDRaster
        
    #
    # ensure a 3d element exists for analysis
    #
    if elevField == '#' and threeDLayer == '#':
        ngp.addwarning('You must have a 3d element available to do the analysis.  See help.')
        return 2
        

    #
    # check out a 3d analyst license
    #
    if ngp.CheckExtension("3d") == "Available":
        ngp.CheckOutExtension("3d")
    else:
        ngp.adderror("3D Analyst License is not available.")
        return 2
    
                               
    #
    # get elevation for input data
    #
    
    if threeDLayer <> '#':
        #
        #  Check to see if spot field exists if so, add another field name "Spot_x"
        #
        spotfield_num = "Spot"
        if ngp.ListFields(inputFea, spotfield_num).Next():
            i = 1
            spotfield_num = "Spot_" + str(i)
            while ngp.ListFields(inputFea, spotfield_num).Next():
                i += 1
                spotfield_num = "Spot_" + str(i)
        elevField = spotfield_num
        
        ngp.workspace = outputwks
            
        if shpType == 'Point':
            ngp.addwarning('Running Point Analysis...')
            # copy source point to oplayer and use oplayer
            ngp.FeatureClassToFeatureClass_conversion(inputFea, outputwks, oplayer)
            ngp.SurfaceSpot_3d(threeDLayer, oplayer, spotfield_num, "1", "BILINEAR")

        elif shpType == 'Polyline':
            ngp.addwarning('Running Polyline Analysis...')
            # create oplayer
            mklineoutput(inputFea, outputwks, pointDensity, oplayer, ngp)
            ngp.SurfaceSpot_3d(threeDLayer, oplayer, spotfield_num, "1", "BILINEAR")
             
        elif shpType == 'Polygon':
            ngp.addwarning('Running Polygon Analysis...')
            #
            #   test to see if density field exists:  Add density field, then calc it
            #
            densityfld = "xdensity"
            if ngp.ListFields(inputFea, densityfld).Next():
                i = 1
                rtid = "xdensity_" + str(i)
                while ngp.ListFields(inputFea, densityfld).Next():
                    i += 1
                    densityfld = "xdensity_" + str(i)
            # add routeid to temporary line   
            ngp.AddField_management(inputFea, densityfld, "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            ngp.CalculateField_management(inputFea, densityfld, "[SHAPE_Area] / " + str(pointDensity), "VB","") 
            
            ngp.CreateRandomPoints_management(outputwks, oplayer, inputFea, "0 0 250 250", str(densityfld))

            if ngp.ListFields(inputFea, densityfld).Next():
                ngp.DeleteField(inputFea, densityfld)
            
            ngp.SurfaceSpot_3d(threeDLayer, oplayer, spotfield_num, "1", "BILINEAR")
    else:
        spotfield_num = elevField
        print str(spotfield_num)
                            
##        ngp.workspace = outputwks
##        if ngp.exists(tempverts):
##            ngp.Delete_management(tempverts)

    #
    # check in the 3d analyst license
    #
    ngp.CheckInExtension("3d")

    #
    # get units of measurment for comment section
    #
    dsc = ngp.describe(oplayer)
    
    #
    # Add reporting fields to output layer
    #
    ngp.addwarning('Adding Fields...')
    ngp.AddField_management(oplayer, "SRGHT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    ngp.AddField_management(oplayer, "TIDEHEIGHT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    ngp.AddField_management(oplayer, "SLR", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    ngp.AddField_management(oplayer, "SEALEVEL", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    ngp.AddField_management(oplayer, "SLVLDLTA", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    ngp.AddField_management(oplayer, "COMMENT", "TEXT", "", "", "320", "", "NULLABLE", "NON_REQUIRED", "")
    
    ngp.addwarning('Calculating Fields...')
    print currentTides
    ngp.CalculateField_management(oplayer, "SRGHT", surgeHeight, "VB", "") 
    ngp.CalculateField_management(oplayer, "TIDEHEIGHT", currentTides, "VB", "")   
    ngp.CalculateField_management(oplayer, "SLR", slrHeight, "VB", "")
    ngp.CalculateField_management(oplayer, "SEALEVEL", "[SRGHT] + [TIDEHEIGHT] + [SLR]", "VB","")
    ngp.CalculateField_management(oplayer, "SLVLDLTA", "[SEALEVEL] - [" + str(spotfield_num) + "]", "VB","") 
    ngp.addmessage()
    # Add comments using cursor
    ucur = ngp.updatecursor(oplayer)
    row = ucur.Next()
    while row:
        slvdelta = row.getvalue("SLVLDLTA")
        absval = abs(slvdelta)
        if slvdelta <= 0:
            row.SetValue ("Comment", 'Above water: Point is ' + str(absval) + ' above sea level.')
            if absval > 30000:
                row.SetValue ("Comment", 'WARNING: The point may not have been within the bounding box of the 3D layer. Above water: Point is ' + str(absval) + ' above sea level.')

        else:
            row.SetValue ("Comment", 'Under water: Point is ' + str(absval) + ' below sea level.')
            if absval > 30000:
                row.SetValue ("Comment", 'WARNING: The point may not have been within the bounding box of the 3D layer. Under water: Point is ' + str(absval) + ' below sea level.')
            
            
        ucur.UpdateRow(row)
        row = ucur.Next()
        
#
#  Process arguments and call layer creation functions.
#
#
def process(args, ingp):
    #
    #   set vars
    #
    tempverts = 'tempverts'
    threeDLayer = '#'
#    outputname = 'sealevelrise'
    logTable = 'SLRLog' + strftime("%Y%m%d_%H%M%S", localtime())

#
# input arguments
#
    # point line poly layer
    inputFea = args[0]

      #
    #   describe input features
    #
    dscInput = ingp.describe(inputFea)
    sr = dscInput.SpatialReference
    shpType = dscInput.ShapeType
    units = dscInput.spatialreference.LinearUnitName
    ingp.addmessage('Linear units: ' + units)
    
    # a point on a line every x along the line
    if args[1] <> "#":
        pointDensity = float(args[1])
    #    lstInputs[1] = pointDensity
    # elevation field from the input if one exists
    elevField = args[2]
    
#
# 3d layer arguments
#       if no 3d field exists w/in input features
#       use one of the following 3d  inputs
#       - TIN
#       - Raster(grid)
#

    threeDTin = args[3]
    threeDRaster = args[4]

#
#   Optional surge height info
#       fill out both for reporting purposes
#
    surgeHeight = str(args[7])
    lstsurgeht = surgeHeight.split(';')
#    lstInputs[7] = 'null'
    

#
#   Tide, Sea leve rise & year, output workspace
#
    currentTides = args[5]
    
    slrHeight = args[6]
    lstslrHt = slrHeight.split(';')
#    lstInputs[6] = 'null'
    
    ovrwrite = args[8]
    outputwks = args[9]
    
# cleanup mess if they pick c:\ or g:\ etc as an output folder
    
    outputwks = outputwks.replace('\"', '\\')
#    lstInputs[9] = outputwks

# output file name
    outputnm = args[10]
    outputnm = outputnm.replace(' ', '')
    
#
#   determine output via type of output workspace  
#
    
    dscOutput = ingp.describe(outputwks)
    
    if dscOutput.WorkspaceType == 'FileSystem':
        # final output is shape
        outputtype = 'shape'
    else:
        #final output featurelayer point
        outputtype = 'featureclass'

#   overwrite outputnm with outputtype
    lstInputs = [inputFea, pointDensity, elevField, threeDTin, threeDRaster, currentTides, 'null', 'null', ovrwrite, outputwks]
    lstInputs.append(outputtype)
    lstInputs.append('')
    lstInputs.append('')
    lstInputs.append(units)


#
#   for each sealevel rise create a point layer
#
    count = 1
    print lstslrHt
    print lstsurgeht
    for slrht in lstslrHt:
#   loop for each optional storm surge
        for srght in lstsurgeht:
            print slrht + ' :: ' + srght
            oplayer =  outputnm + '_' + str(count)          
            
        #
        #   overwrite or create a new name for oplayer
        #
            ingp.workspace = outputwks
            print str(outputwks)
            print ovrwrite
            if ovrwrite == 'true':
                print oplayer
                print ingp.exists(oplayer)
                if outputtype == 'shape':
                    oplayer = oplayer + '.shp'
                else:
                    oplayer = oplayer
                if ingp.exists(oplayer):
                    print 'Deleting...' + oplayer
                    ingp.Delete_management(oplayer)
                    print 'Deleted...' + oplayer
            elif ovrwrite == 'false':
                if ingp.exists(oplayer):
                    ingp.addwarning(oplayer + ' already exists.')
                    outputroot = outputnm + '_'
                    i = 1
                    oplayer = outputroot + str(i)
                    while ingp.exists(oplayer):
                        i += 1
                        oplayer = outputroot + str(i)
                            
            ingp.addwarning("------------")
            ingp.addwarning(oplayer)
            count += 1
            lstInputs[11] = oplayer
            # Storm Surge is an optional input
            if surgeHeight == '#':
                srght = 0
                
            
##            ingp.addwarning(shpType)
##            ingp.addwarning(sr.name)
##            ingp.addwarning(sr.LinearUnitName)

            lstInputs[12] = shpType
            lstInputs[6] = slrht
            lstInputs[7] = srght
            logrecord = [oplayer, srght, currentTides, slrht]
            #
            #   call createlayer
            #
            print lstInputs
            createLayer(lstInputs, ingp)
            writeLogTable(logTable, outputwks, logrecord, ingp)


#
# Run the main function
#
if __name__ == "__main__":
    try:
        sys.exit(main())
    except:
       print ""

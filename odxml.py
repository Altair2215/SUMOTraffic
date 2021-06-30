from csv import reader
from os import getcwd
from os import listdir
from os import makedirs
from os import path
from os import system
from shutil import copyfile
from xml.dom import minidom
from xml.etree.ElementTree import parse

import matplotlib.pyplot as plt
import numpy
from dbfread import DBF
from scipy import stats
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from sumolib import net


def id(edge, passe):
    if 'type' not in edge.attrib or 'name' not in edge.attrib:
        return False
    if 'priority' in edge.attrib and edge.attrib['type'] in passe:
        return True
    return False


def passenger(root):
    idtype = []
    for type in root.iter('type'):
        if "allow" in type.attrib:
            if 'passenger' in type.attrib["allow"].split(" "):
                idtype.append(type.attrib["id"])
        if "disallow" in type.attrib:
            if 'passenger' not in type.attrib["disallow"].split(" "):
                idtype.append(type.attrib["id"])
    return idtype


def fnet():
    osmget = []
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        makedirs(getcwd() + "/ODMatrix/" + file + "/" + grid, exist_ok=True)
        tree = parse("wkt.netccfg")
        root = tree.getroot()
        for files in root.iter():
            if files.tag == 'osm-files':
                files.set('value', getcwd() + "/ODMatrix/" + file + "/" + grid + '/wkt_bbox.osm.xml')
            if files.tag == 'output-file':
                files.set('value', getcwd() + "/ODMatrix/" + file + "/" + grid + '/wkt.net.xml')
        tree.write(getcwd() + "/ODMatrix/" + file + "/" + grid + "/wkt.netccfg")
        tree = parse("wkt.polycfg")
        root = tree.getroot()
        for files in root.iter():
            if files.tag == 'osm-files':
                files.set('value', getcwd() + "/ODMatrix/" + file + "/" + grid + '/wkt_bbox.osm.xml')
            if files.tag == 'net-file':
                files.set('value', getcwd() + "/ODMatrix/" + file + "/" + grid + '/wkt.net.xml')
            if files.tag == 'output-file':
                files.set('value', getcwd() + "/ODMatrix/" + file + "/" + grid + '/wkt.poly.xml')
        tree.write(getcwd() + "/ODMatrix/" + file + "/" + grid + "/wkt.polycfg")
        with open("ODMatrix/" + file + '/latlon.csv') as csv_file:
            csv_reader = list(reader(csv_file, delimiter='\t'))
            for row in csv_reader[1:]:
                temp = []
                poly = tuple(row[0].replace("((", "").replace("))", "").replace(",", "").split(" ")[1:])
                index = 0
                for number in poly:
                    if index == 0 or index == 1 or index == 4 or index == 5:
                        temp.append(round(float(number), 4))
                    index += 1
                if not osmget:
                    osmget = temp
                else:
                    for i in range(0, len(osmget)):
                        if i in (0, 1) and temp[i] < osmget[i]:
                            osmget[i] = temp[i]
                        if i in (2, 3) and temp[i] > osmget[i]:
                            osmget[i] = temp[i]
        if not path.exists("ODMatrix/" + file + "/" + grid + '/wkt_bbox.osm.xml'):
            system('osmGet.py -d ' + getcwd() + "/ODMatrix/" + file + "/" + grid + ' -p wkt -b '
                   + str(osmget[0]) + "," + str(osmget[1]) + "," + str(osmget[2]) + "," + str(osmget[3]))
        if not path.exists("ODMatrix/" + file + "/" + grid + '/wkt.net.xml'):
            system("netconvert -c " + getcwd() + "/ODMatrix/" + file + "/" + grid + "/wkt.netccfg")
            system("polyconvert -c " + getcwd() + "/ODMatrix/" + file + "/" + grid + "/wkt.polycfg")


def wtaz():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        if not path.exists("ODMatrix/" + file + "/" + grid + '/wkt.taz.xml'):
            osmnet = net.readNet("ODMatrix/" + file + "/" + grid + '/wkt.net.xml')
            xmlroot = minidom.Document()

            xml = xmlroot.createElement('additional')
            xmlroot.appendChild(xml)
            tree = parse("ODMatrix/" + file + "/" + grid + '/wkt.net.xml')
            root = tree.getroot()
            passe = passenger(root)
            tazs = xmlroot.createElement('tazs')
            with open("ODMatrix/" + file + '/latlon.csv') as csv_file:
                csv_reader = list(reader(csv_file, delimiter='\t'))
                for row in csv_reader[1:]:
                    taz = xmlroot.createElement('taz')
                    taz.setAttribute('id', row[1])
                    tazedge = ""
                    poly = tuple(row[0].replace("((", "").replace("))", "").replace(",", "").split(" ")[1:])
                    polygon = Polygon([(round(float(poly[0]), 4), round(float(poly[1]), 4)),
                                       (round(float(poly[2]), 4), round(float(poly[3]), 4)),
                                       (round(float(poly[4]), 4), round(float(poly[5]), 4)),
                                       (round(float(poly[6]), 4), round(float(poly[7]), 4))])
                    for edge in root.iter('edge'):
                        if id(edge, passe):
                            inside = 0
                            shape = edge.find('lane').attrib['shape'].split(" ")
                            for pos in shape:
                                lon, lat = osmnet.convertXY2LonLat(round(float(pos.split(",")[0]), 4),
                                                                   round(float(pos.split(",")[1]), 4))
                                point = Point(lon, lat)
                                if polygon.contains(point):
                                    inside += 1
                            if inside / len(shape) >= 0.50:
                                if not tazedge:
                                    tazedge = edge.attrib['id']
                                elif edge.attrib['id'] not in tazedge:
                                    tazedge += " " + edge.attrib['id']
                    if tazedge == "":
                        continue
                    taz.setAttribute('edges', tazedge)
                    tazs.appendChild(taz)
            xml.appendChild(tazs)

            xml_str = xmlroot.toprettyxml(indent="\t")

            save_path_file = "ODMatrix/" + file + "/" + grid + "/wkt.taz.xml"

            with open(save_path_file, "w") as f:
                f.write(xml_str)


def wod():
    for file in listdir("ODMatrix"):
        for odcsv in listdir("ODMatrix/" + file):
            grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
            if odcsv[:2] == "od" and not odcsv.replace(".csv", "").split("-")[3] == "0":
                with open("ODMatrix/" + file + "/" + odcsv) as csv_file:
                    csv_reader = list(reader(csv_file, delimiter='\t'))
                    odline = ""
                    for row in csv_reader[15:]:
                        index = 1
                        for number in row[1:]:
                            if not number == "0.0":
                                odline += row[0] + " " + csv_reader[14][index] + " " + number + "\n"
                            index += 1
                    filename = odcsv.replace(".csv", "").split("-")[1] + "-H-" + \
                               odcsv.replace(".csv", "").split("-")[2]
                    makedirs(getcwd() + "/ODMatrix/" + file + "/" + grid + "/SUMO/" + filename, exist_ok=True)
                    odfile = open("ODMatrix/" + file + "/" + grid + "/SUMO/" + filename + "/" + filename
                                  + ".od", 'w')
                    odfile.write('$O;D2\n'
                                 '0.00 1.00\n'
                                 '1\n'
                                 + odline
                                 )
                    odfile.close()


def config():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            xmlroot = minidom.Document()

            xml = xmlroot.createElement('configuration')
            xmlroot.appendChild(xml)

            i = xmlroot.createElement('input')
            tazf = xmlroot.createElement('taz-files')
            tazf.setAttribute('value', "../../wkt.taz.xml")
            odm = xmlroot.createElement('od-matrix-files')
            odm.setAttribute('value', od + '.od')
            i.appendChild(tazf)
            i.appendChild(odm)
            xml.appendChild(i)

            o = xmlroot.createElement('output')
            outf = xmlroot.createElement('output-file')
            outf.setAttribute('value', od + ".odtrips.xml")
            o.appendChild(outf)
            xml.appendChild(o)

            xml_str = xmlroot.toprettyxml(indent="\t")

            save_path_file = "ODMatrix/" + file + "/" + grid + "/SUMO/" + od + "/" + od + ".config.xml"

            with open(save_path_file, "w") as f:
                f.write(xml_str)


def duarcfg():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            xmlroot = minidom.Document()

            xml = xmlroot.createElement('configuration')
            xmlroot.appendChild(xml)

            i = xmlroot.createElement('input')
            tazf = xmlroot.createElement('net-file')
            tazf.setAttribute('value', "../../wkt.net.xml")
            odm = xmlroot.createElement('route-files')
            odm.setAttribute('value', od + '.odtrips.xml')
            i.appendChild(tazf)
            i.appendChild(odm)
            xml.appendChild(i)

            o = xmlroot.createElement('output')
            outf = xmlroot.createElement('output-file')
            outf.setAttribute('value', od + ".odtrips.rou.xml")
            o.appendChild(outf)
            xml.appendChild(o)

            r = xmlroot.createElement('report')
            v = xmlroot.createElement('verbose')
            v.setAttribute('value', "false")
            r.appendChild(v)
            xmlv = xmlroot.createElement('xml-validation')
            xmlv.setAttribute('value', "never")
            r.appendChild(xmlv)
            nsl = xmlroot.createElement('no-step-log')
            nsl.setAttribute('value', "true")
            r.appendChild(nsl)
            ie = xmlroot.createElement('ignore-errors')
            ie.setAttribute('value', "true")
            r.appendChild(ie)
            xml.appendChild(r)

            p = xmlroot.createElement('processing')
            rp = xmlroot.createElement('repair')
            rp.setAttribute('value', "true")
            p.appendChild(rp)
            rf = xmlroot.createElement('repair.from')
            rf.setAttribute('value', "true")
            p.appendChild(rf)
            rt = xmlroot.createElement('repair.to')
            rt.setAttribute('value', "true")
            p.appendChild(rt)
            xml.appendChild(p)

            xml_str = xmlroot.toprettyxml(indent="\t")

            save_path_file = "ODMatrix/" + file + "/" + grid + "/SUMO/" + od + "/" + od + ".trips2routes.duarcfg"

            with open(save_path_file, "w") as f:
                f.write(xml_str)


def od2trips():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            if not path.exists('ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/" + od + ".odtrips.xml"):
                system('od2trips -c ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/" + od + ".config.xml "
                                                                                                "--ignore-errors")


def duarouter():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            if not path.exists('ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/" + od + ".odtrips.rou.xml"):
                system('duarouter -c ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/" + od +
                       '.trips2routes.duarcfg')


def view():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        xmlroot = minidom.Document()

        xml = xmlroot.createElement('viewsettings')
        xmlroot.appendChild(xml)

        sch = xmlroot.createElement('scheme')
        sch.setAttribute('name', "real world")
        xml.appendChild(sch)
        delay = xmlroot.createElement('delay')
        delay.setAttribute('value', "0")
        xml.appendChild(delay)

        xml_str = xmlroot.toprettyxml(indent="\t")

        save_path_file = "ODMatrix/" + file + "/" + grid + "/wkt.view.xml"

        with open(save_path_file, "w") as f:
            f.write(xml_str)


def addfile():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            xmlroot = minidom.Document()

            xml = xmlroot.createElement('additional')
            xmlroot.appendChild(xml)

            edgedata = xmlroot.createElement('edgeData')
            edgedata.setAttribute('id', "traffic")
            edgedata.setAttribute('file', "traffic.xml")
            edgedata.setAttribute('excludeEmpty', "true")
            xml.appendChild(edgedata)
            co2 = xmlroot.createElement('edgeData')
            co2.setAttribute('id', "emissions")
            co2.setAttribute('type', "emissions")
            co2.setAttribute('file', "emissions.xml")
            co2.setAttribute('excludeEmpty', 'true')
            xml.appendChild(co2)

            xml_str = xmlroot.toprettyxml(indent="\t")

            save_path_file = "ODMatrix/" + file + "/" + grid + "/SUMO/" + od + "/wkt.add.xml"

            with open(save_path_file, "w") as f:
                f.write(xml_str)


def sumocfg():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            xmlroot = minidom.Document()

            xml = xmlroot.createElement('configuration')
            xmlroot.appendChild(xml)

            i = xmlroot.createElement('input')
            tazf = xmlroot.createElement('net-file')
            tazf.setAttribute('value', "../../wkt.net.xml")
            i.appendChild(tazf)
            odm = xmlroot.createElement('route-files')
            odm.setAttribute('value', od + '.odtrips.rou.xml')
            i.appendChild(odm)
            adf = xmlroot.createElement('additional-files')
            adf.setAttribute('value', 'wkt.add.xml,../../wkt.poly.xml')
            i.appendChild(adf)
            xml.appendChild(i)

            o = xmlroot.createElement('processing')
            ire = xmlroot.createElement('ignore-route-errors')
            ire.setAttribute('value', "true")
            o.appendChild(ire)
            xml.appendChild(o)

            r = xmlroot.createElement('routing')
            dras = xmlroot.createElement('device.rerouting.adaptation-steps')
            dras.setAttribute('value', "18")
            r.appendChild(dras)
            drai = xmlroot.createElement('device.rerouting.adaptation-interval')
            drai.setAttribute('value', "10")
            r.appendChild(drai)
            xml.appendChild(r)

            rt = xmlroot.createElement('report')
            v = xmlroot.createElement('verbose')
            v.setAttribute('value', "true")
            rt.appendChild(v)
            dls = xmlroot.createElement('duration-log.statistics')
            dls.setAttribute('value', 'true')
            rt.appendChild(dls)
            nsl = xmlroot.createElement('no-step-log')
            nsl.setAttribute('value', 'true')
            rt.appendChild(nsl)
            xml.appendChild(rt)

            go = xmlroot.createElement('gui_only')
            gsf = xmlroot.createElement('gui-settings-file')
            gsf.setAttribute('value', "../../wkt.view.xml")
            go.appendChild(gsf)
            xml.appendChild(go)

            out = xmlroot.createElement('output')
            trip = xmlroot.createElement('tripinfo-output')
            trip.setAttribute('value', "tripinfos.xml")
            out.appendChild(trip)
            trip = xmlroot.createElement('tripinfo-output.write-unfinished')
            trip.setAttribute('value', "true")
            out.appendChild(trip)
            xml.appendChild(out)

            xml_str = xmlroot.toprettyxml(indent="\t")

            save_path_file = "ODMatrix/" + file + "/" + grid + "/SUMO/" + od + "/" + od + ".sumocfg"

            with open(save_path_file, "w") as f:
                f.write(xml_str)


def giornotraffic():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        gtraffic = {}
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            tree = parse("ODMatrix/" + file + "/" + grid + "/SUMO/" + od + "/traffic.xml")
            root = tree.getroot()
            m = "entered"
            for edge in root.iter("edge"):
                if edge.attrib["id"] in gtraffic.keys():
                    gtraffic.update({edge.attrib["id"]: int(gtraffic.get(edge.attrib["id"])) + int(edge.attrib[m])})
                else:
                    gtraffic.update({edge.attrib["id"]: int(edge.attrib[m])})
        xmlroot = minidom.Document()

        xml = xmlroot.createElement('interval')
        xml.setAttribute('begin', '0')
        xml.setAttribute('end', '3600')
        xml.setAttribute('id', 'traffic')
        xmlroot.appendChild(xml)
        for edge in gtraffic:
            edgedata = xmlroot.createElement('edge')
            edgedata.setAttribute('id', edge)
            edgedata.setAttribute('entered', str(gtraffic[edge]))
            xml.appendChild(edgedata)

        xml_str = xmlroot.toprettyxml(indent="\t")

        save_path_file = "ODMatrix/" + file + "/" + grid + "/" + grid + ".traffic.xml"

        with open(save_path_file, "w") as f:
            f.write(xml_str)


def mediatraffic():
    makedirs(getcwd() + "/ReggioTraffic/10", exist_ok=True)
    makedirs(getcwd() + "/ReggioTraffic/20", exist_ok=True)
    copyfile(
        "ODMatrix/ODMatrixTime_pls_anagrafica_20170223.gz_ReggioEmiliaArea10_23-02-2017_24/10_23-02-2017/wkt.net.xml",
        "ReggioTraffic/10/wkt.net.xml")
    copyfile(
        "ODMatrix/ODMatrixTime_pls_anagrafica_20170223.gz_ReggioEmiliaArea20_23-02-2017_24/20_23-02-2017/wkt.net.xml",
        "ReggioTraffic/20/wkt.net.xml")
    m10traffic = {}
    m20traffic = {}
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        precision = grid[:2]
        tree = parse("ODMatrix/" + file + "/" + grid + "/" + grid + ".traffic.xml")
        root = tree.getroot()
        m = "entered"
        for edge in root.iter("edge"):
            if edge.attrib["id"] in locals()["m" + precision + "traffic"].keys():
                locals()["m" + precision + "traffic"].update(
                    {edge.attrib["id"]: int(locals()["m" + precision + "traffic"].get(edge.attrib["id"])) + int(
                        edge.attrib[m])})
            else:
                locals()["m" + precision + "traffic"].update({edge.attrib["id"]: int(edge.attrib[m])})
    for file in listdir("ReggioTraffic"):
        xmlroot = minidom.Document()

        xml = xmlroot.createElement('interval')
        xml.setAttribute('begin', '0')
        xml.setAttribute('end', '3600')
        xml.setAttribute('id', 'traffic')
        xmlroot.appendChild(xml)
        for edge in locals()["m" + file + "traffic"]:
            edgedata = xmlroot.createElement('edge')
            edgedata.setAttribute('id', edge)
            edgedata.setAttribute('entered', str(round(locals()["m" + file + "traffic"][edge] / 6)))
            xml.appendChild(edgedata)

        xml_str = xmlroot.toprettyxml(indent="\t")

        save_path_file = "ReggioTraffic/" + file + "/" + file + "reggio.traffic.xml"

        with open(save_path_file, "w") as f:
            f.write(xml_str)


def sumocmd():
    for file in listdir("ODMatrix"):
        grid = file.split("_")[4][-2:] + "_" + file.split("_")[5]
        for od in listdir("ODMatrix/" + file + "/" + grid + "/SUMO"):
            if not path.exists('ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/traffic.xml"):
                system('sumo -c ODMatrix/' + file + "/" + grid + "/SUMO/" + od + "/" + od + ".sumocfg")


def autostrada(idnumber):
    auto = [544, 625, 543, 540, 624, 623, 626, 538, 542, 541, 537, 539]
    if idnumber not in auto:
        return True


def dbfread():
    road = {}
    for record in DBF('reteurbanaflussitraffico/ReteUrbana_flussi-traffico.dbf'):
        if autostrada(int(record["STRADA"])):
            road.update({str(record["INIZIO"]) + "-" + str(record["FINE"]): record["Veq_A"] + record["Veq_R"]})
    tree = parse("reteurbanaflussitraffico/osm.net.xml")
    root = tree.getroot()
    split = {}
    for edge in root.iter("edge"):
        if "from" not in edge.attrib or "to" not in edge.attrib:
            continue
        if edge.attrib["from"] + "-" + edge.attrib["to"] in road:
            split.update({edge.attrib["id"]: road[edge.attrib["from"] + "-" + edge.attrib["to"]]})
    xmlroot = minidom.Document()

    xml = xmlroot.createElement('interval')
    xml.setAttribute('begin', '0')
    xml.setAttribute('end', '3600')
    xml.setAttribute('id', 'traffic')
    xmlroot.appendChild(xml)
    for edge in split:
        edgedata = xmlroot.createElement('edge')
        edgedata.setAttribute('id', edge)
        edgedata.setAttribute('entered', str(split[edge]))
        xml.appendChild(edgedata)

    xml_str = xmlroot.toprettyxml(indent="\t")

    save_path_file = "reteurbanaflussitraffico/dbftraffic.xml"

    with open(save_path_file, "w") as f:
        f.write(xml_str)


def dbfnet():
    system(
        "netconvert "
        "--shapefile-prefix reteurbanaflussitraffico/ReteUrbana_flussi-traffico "
        "-o reteurbanaflussitraffico/osm.net.xml "
        "--shapefile.street-id STRADA --shapefile.from-id INIZIO "
        "--shapefile.to-id FINE --shapefile.use-defaults-on-failure")


def confronto():
    osmnet = net.readNet("reteurbanaflussitraffico/osm.net.xml")
    tree = parse("reteurbanaflussitraffico/osm.net.xml")
    root = tree.getroot()
    for edge in root.iter('edge'):
        if "shape" in edge.attrib:
            shape = edge.attrib["shape"].split(" ")
        else:
            shape = edge.find('lane').attrib['shape'].split(" ")
        if edge.attrib["id"] == "218":
            for pos in shape:
                lat, lon = osmnet.convertXY2LonLat(float(pos.split(",")[0]),
                                                   float(pos.split(",")[1]))
                print(lat, lon)
    x = []
    y = []
    with open('confronto.txt') as f:
        lines = f.readlines()
    tree = parse("reteurbanaflussitraffico/dbftraffic.xml")
    root = tree.getroot()
    osmstreet = 0
    wktstreet = 0
    osmtot = len(root)
    for idedges in lines:
        temp = 0
        for idedge in idedges.split("||")[0].split(" "):
            for edge in root.iter("edge"):
                if edge.attrib["id"] == idedge:
                    temp += int(edge.attrib["entered"])
                    osmstreet += 1
        x.append(round(temp / len(idedges.split("||")[0].split(" "))))
    tree = parse("ReggioTraffic/10/10reggio.traffic.xml")
    root = tree.getroot()
    wkttot = len(root)
    osmnet = net.readNet('ReggioTraffic/10/wkt.net.xml')
    for idedges in lines:
        temp = 0
        for idedge in idedges.split("||")[1].split(" "):
            for edge in root.iter("edge"):
                osmnet.getEdge(idedge.replace("\n", ""))
                if edge.attrib["id"] == idedge.replace("\n", ""):
                    temp += int(edge.attrib["entered"])
                    wktstreet += 1
        y.append(round(temp / len(idedges.split("||")[1].split(" "))))
    print(osmstreet, round(osmstreet / osmtot * 100, 2), wktstreet, round(wktstreet / wkttot * 100, 2), len(x))
    plt.scatter(x, y, c='black', alpha=0.5)
    z = numpy.polyfit(x, y, 1)
    p = numpy.poly1d(z)
    plt.plot(x, p(x), "r--")
    plt.show()
    print(stats.pearsonr(x, y))


def istat():
    with open('MATRICE_PENDOLARISMO_2011/matrix_pendo2011_10112014.txt') as f:
        lines = f.readlines()
    tot = 0
    for pend in lines:
        if pend.split(" ")[2] == "035":
            if pend.split(" ")[3] in (
                    "001", "002", "004", "008", "010", "015", "017", "018", "022", "027", "029", "030", "033", "036",
                    "038", "039", "040", "043", "044"):
                if pend.split(" ")[7] == "1":
                    if pend.split(" ")[11] in ("07", "08"):
                        tot += 1
    if not path.exists("MATRICE_PENDOLARISMO_2011/SUMO/wkt.odtrips.rou.xml"):
        system(
            "randomTrips.py -n MATRICE_PENDOLARISMO_2011/SUMO/wkt.net.xml -e " + str(tot)
            + " --route-file MATRICE_PENDOLARISMO_2011/SUMO/wkt.odtrips.rou.xml")
    if not path.exists("MATRICE_PENDOLARISMO_2011/SUMO/traffic.xml"):
        system("sumo -c MATRICE_PENDOLARISMO_2011/SUMO/sumo.sumocfg")
    x = []
    y = []
    mtree = parse("MATRICE_PENDOLARISMO_2011/SUMO/traffic.xml")
    mroot = mtree.getroot()
    tree = parse("ReggioTraffic/10/10reggio.traffic.xml")
    root = tree.getroot()
    for medge in mroot.iter("edge"):
        for edge in root.iter("edge"):
            if medge.attrib["id"] == edge.attrib["id"]:
                x.append(int(medge.attrib["entered"]))
                y.append(int(edge.attrib["entered"]))
    plt.scatter(x, y, c='black', alpha=0.5)
    z = numpy.polyfit(x, y, 1)
    p = numpy.poly1d(z)
    plt.plot(x, p(x), "r--")
    plt.show()
    print(stats.pearsonr(x, y))

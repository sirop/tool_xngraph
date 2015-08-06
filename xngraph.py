#!/usr/bin/python

"""

xngraph - XN Graph: Produce a graph description of an XMOS XN file

DOT output contains nodes with the name, followed by frequencies ( Osc / Ref /
Sys) plus links with their link properties defined as ( wires, tokdelay,
symdelay )

Author: Steve Kerrison <steve.kerrison@bristol.ac.uk>, January 2014

Usage:
    xngraph.py [options] <xnfile>

Options:
    --ignore-nodes <node1,node2,...,nodeN>        Ignore specified node names

Arguments:
    <xnfile>     The XN file containing node and link info for a platform

"""

"""
    XN Graph: Produce a graph description of an XMOS XN file
    Copyright (C) 2014 Steve Kerrison

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

from docopt import docopt
import xml.etree.ElementTree as ET
import re
import pexpect


class XNReader:
    # XMOS XN file namespace
    NS = 'http://www.xmos.com'
    common_tilerefs = ['stdcore', 'stdtile', 'tile']
    linkmap = {
        'A': 2,
        'B': 3,
        'C': 0,
        'D': 1,
        'E': 6,
        'F': 7,
        'G': 4,
        'H': 5
    }

    def extract(self, XEFilename):
        secscan = pexpect.run('xesection {}'.format(XEFilename))
        match = re.search(r'^Sector ([0-9]+): type: 8', secscan, re.M)
        xndata = pexpect.run(
            'xesection {} {}'.format(XEFilename, match.group(1)))
        return xndata[xndata.find('<'):-5]

    def __init__(self, XNFilename, ignorenodes=[], tilerefs=[]):
        if XNFilename[-3:] == '.xe':
                t = ET.fromstring(self.extract(XNFilename))
        else:
                t = ET.parse(XNFilename)
        self.nodes = {}
        self.links = []
        self.tilerefs = XNReader.common_tilerefs + tilerefs
        if not ignorenodes:
            ignorenodes = []
        if 'getroot' not in t:
            root = t
        else:
            root = t.getroot()
        if root.tag != '{{{}}}Network'.format(XNReader.NS):
            raise Exception('Invalid namespace, should be {}'.format(
                XNReader.NS))
        for Node in [x for x in t.iter('{{{}}}Node'.format(XNReader.NS))
                     if x.attrib['Id'] not in ignorenodes
                     and not ("Type" in x.attrib and x.attrib['Type'] ==
                              "device:")]:
            attrs = {'Oscillator': 20e6, 'SystemFrequency': 400e6,
                     'ReferenceFrequency': 100e6, 'ref': Node.attrib['Id']}
            attrs.update([(x, self.FreqConv(Node.attrib[x])) for x in
                          attrs.keys() if x in Node.attrib])
            if 'RoutingId' in Node.attrib:
                attrs['RoutingId'] = Node.attrib['RoutingId']
            if 'Type' in Node.attrib and Node.attrib['Type'][:7] == 'periph:':
                attrs['p'] = True
            for core in Node.iter('{{{}}}Core'.format(XNReader.NS)):
                m = re.search(
                    r'\[(.*?)\]', core.attrib.get(
                        'Reference', 'tile[{}]'.format(Node.attrib['Id'])))
                attrs['ref'] = int(m.group(1))
                break  # To-do, if we ever have multi-core nodes, handle them!
            self.nodes[Node.attrib['Id']] = attrs
        for Link in t.iter('{{{}}}Link'.format(XNReader.NS)):
            if ('Flags' in Link.attrib
                    and Link.attrib['Flags'] in ["SOD", "XSCOPE"]):
                continue  # Skip XScope!
            if 'direction' in Link.attrib:
                continue  # Skip directional link data
            if 'Encoding' in Link.attrib:
                encoding = Link.attrib['Encoding'][0]
            else:
                encoding = '2'
            if 'Delays' in Link.attrib:
                delays = Link.attrib['Delays'].replace('clk', '')
            Ends = Link.findall('{{{}}}LinkEndpoint'.format(XNReader.NS))
            if any(map(lambda(x): x.attrib['NodeId'] in ignorenodes, Ends)):
                continue  # Skip links involving ignored nodes
            if 'Delays' in Ends[0].attrib:
                ldelay = Ends[0].attrib['Delays'].replace('clk', '')
            else:
                ldelay = delays
            self.links.append({'src': Ends[0].attrib['NodeId'], 'dst':
                               Ends[1].attrib['NodeId'], 'num':
                               self.linkmap[Ends[0].attrib['Link'][-1]],
                               'attr': {'enc': encoding, 'del': ldelay}})
            if 'Delays' in Ends[1].attrib:
                ldelay = Ends[1].attrib['Delays'].replace('clk', '')
            else:
                ldelay = delays
            self.links.append({'src': Ends[1].attrib['NodeId'], 'dst':
                               Ends[0].attrib['NodeId'], 'num':
                               self.linkmap[Ends[1].attrib['Link'][-1]],
                               'attr': {'enc': encoding, 'del': ldelay}})

    def FreqConv(self, value):
        """Convert frequencies with (M|K)Hz in them to floats"""
        conv = {'m': 1e6, 'k': 1e3}
        m = re.match(r"([0-9\.]+)\s*(.)?(hz)?", str(value).lower())
        ret = float(m.group(1))
        if m.group(2) in conv:
            ret *= conv[m.group(2)]
        return ret

if __name__ == '__main__':
    arguments = docopt(__doc__)
    ign = []
    if arguments['--ignore-nodes']:
        ign = arguments['--ignore-nodes'].split(',')
    XNR = XNReader(arguments['<xnfile>'], ign)
    # Initial DOT setup
    print 'digraph "{}" {{'.format(
        ''.join(arguments['<xnfile>'].split('.')[:-1]))
    print '    rankdir=LR'
    for n, a in XNR.nodes.items():
        if 'p' in a and a['p']:
            realname = n + ' (periph)'
        elif 'ref' in a and n != str(a['ref']):
            realname = '{} [{}]'.format(n, a['ref'])
        else:
            realname = n
        print """    "{0}" [
        shape = "record"
        label = "{4} | {1:e} / {2:e} / {3:e}"
    ];
        """.format(n, a['Oscillator'], a['ReferenceFrequency'],
                   a['SystemFrequency'], realname)
    for l in XNR.links:
        print """    {} -> {} [label="{},{}"];""".format(
            l['src'], l['dst'], l['attr']['enc'], l['attr']['del'])
    print '}'

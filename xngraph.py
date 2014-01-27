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
  --ignore-nodes <node1,node2,...,nodeN>    Ignore specified node names

Arguments:
  <xnfile>   The XN file containing node and link info for a platform

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
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License along
  with this program; if not, write to the Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

from docopt import docopt
import xml.etree.ElementTree as ET
import re

class XNReader:
  # XMOS XN file namespace
  NS = 'http://www.xmos.com'

  def __init__(self,XNFilename,ignorenodes=[]):
    t = ET.parse(XNFilename)
    self.nodes = {}
    self.links = []
    if t.getroot().tag != '{{{}}}Network'.format(XNReader.NS):
      raise Exception('Invalid namespace, should be {}'.format(XNReader.NS))
    for Node in [ x for x in t.iter('{{{}}}Node'.format(XNReader.NS))
      if x.attrib['Id'] not in ign ]:
      freqs = { 'Oscillator': 20e6,
        'SystemFrequency': 400e6,
        'ReferenceFrequency': 100e6 }
      freqs.update( [(x,self.FreqConv(Node.attrib[x]))
        for x in freqs.keys() if x in Node.attrib] )
      self.nodes[Node.attrib['Id']] = freqs
    for Link in t.iter('{{{}}}Link'.format(XNReader.NS)):
      if 'Flags' in Link.attrib and Link.attrib['Flags'] in ["SOD","XSCOPE"]:
        continue #Skip XScope!
      encoding = Link.attrib['Encoding'][0]
      if 'Delays' in Link.attrib:
        delays = Link.attrib['Delays']
      Ends = Link.findall('{{{}}}LinkEndpoint'.format(XNReader.NS))
      if any(map(lambda(x): x.attrib['NodeId'] in ign, Ends)):
        continue #Skip links involving ignored nodes
      if 'Delays' in Ends[0].attrib:
        ldelay = Ends[0].attrib['Delays']
      else:
        ldelay = delays
      self.links.append({'src':Ends[0].attrib['NodeId'],
        'dst': Ends[1].attrib['NodeId'],
        'enc': encoding,
        'del': ldelay})
      if 'Delays' in Ends[1].attrib:
        ldelay = Ends[1].attrib['Delays']
      else:
        ldelay = delays
      self.links.append({'src':Ends[1].attrib['NodeId'],
        'dst': Ends[0].attrib['NodeId'],
        'enc': encoding,
        'del': ldelay})
  
  def FreqConv(self,value):
    """Convert frequencies with (M|K)Hz in them to floats"""
    conv = { 'm' : 1e6,
      'k' : 1e3 }
    m = re.match(r"([0-9\.]+)\s*(.)?(hz)?",str(value).lower())
    ret = float(m.group(1))
    if m.group(2) in conv:
      ret *= conv[m.group(2)]
    return ret

if __name__ == '__main__':
  arguments = docopt(__doc__)
  ign = []
  if arguments['--ignore-nodes']:
    ign = arguments['--ignore-nodes'].split(',')
  XNR = XNReader(arguments['<xnfile>'],ign)
  # Initial DOT setup
  print 'digraph {} {{'.format(''.join(arguments['<xnfile>'].split('.')[:-1]))
  print '  rankdir=LR'
  for n,a in XNR.nodes.items():
    print """  "{0}" [
    shape = "record"
    label = "{0} | {1:e} / {2:e} / {3:e}"
  ];
    """.format(n,a['Oscillator'],a['ReferenceFrequency'],a['SystemFrequency'])
  for l in XNR.links:
    print """  {} -> {} [label="{},{}"];""".format(l['src'],l['dst'], l['enc'],
      l['del'])
  print '}'

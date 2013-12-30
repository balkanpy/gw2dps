"""
UI Configuration file parser
"""
from ConfigParser import SafeConfigParser

def config(fname, section, additional_dct=None):
        parser = SafeConfigParser()
        parser.read(fname)

        items = ['font',
                 'size',
                 'typeface',
                 'color',
                 'charwidth',
                 'background']

        tk_kwargs_map = { 'bg' : 'background',
                          'width': 'charwidth',
                          'fg':'color'}

        dct = { item: parser.get(section, item)
                for item in items \
                if parser.has_option(section, item)}

        rtn = {}

        rtn['font'] = ( dct.get('font', None),
                        dct.get('size', 9),
                        dct.get('typeface', ''))

        for kwarg, name in tk_kwargs_map.iteritems():
            if name in dct:
                rtn[kwarg] = dct.get(name, None)

        alpha = 1

        if parser.has_option(section, 'alpha'):
            alpha = parser.get(section, 'alpha')

        if additional_dct:
            for add in additional_dct:
                if parser.has_option(section, add):
                    additional_dct[add] = parser.get(section, add)

        return rtn, alpha

# -*- coding: utf-8 -*-
## $Id$
## Deal with Bibformat configuraion files.

## This file is part of CDS Invenio.
## Copyright (C) 2002, 2003, 2004, 2005 CERN.
##
## The CDSware is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## The CDSware is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with CDSware; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

__lastupdated__ = """$Date$"""

import os
import re
import stat
import time

from invenio.config import cdslang, weburl, etcdir
from invenio.bibformat_config import templates_path, outputs_path, elements_path, format_template_extension
from invenio.urlutils import wash_url_argument
from invenio.errorlib import get_msgs_for_code_list
from invenio.messages import gettext_set_language, wash_language, language_list_long
from invenio.search_engine import perform_request_search, encode_for_xml
from invenio import bibformat_dblayer
from invenio import bibformat_engine

import invenio.template
bibformat_templates = invenio.template.load('bibformat')

def getnavtrail(previous = '', ln=cdslang):
    """Get the navtrail"""
    previous = wash_url_argument(previous, 'str')
    ln = wash_language(ln)
    _ = gettext_set_language(ln)
    navtrail = '''<a class=navtrail href="%s/admin/index.%s.html">%s</a> &gt; <a class=navtrail href="%s/admin/bibformat/bibformatadmin.py/?ln=%s">%s</a> ''' % (weburl, ln, _("Admin Area"), weburl, ln,  _("BibFormat Admin"))
    navtrail = navtrail + previous
    return navtrail

def perform_request_index(version="", ln=cdslang, warnings=None):
    """
    Returns the main BibFormat admin page.

    The page offers for some times the choice between the old and new BibFormat.
    This is the only page where the code needs to be cleaned
    when the migration kit will be removed. #TODO: remove when removing migration_kit
    
   
    @param ln language
    @param version the version of BibFormat to use ('new'|'old')
    @param warnings a list of messages to display at top of the page, that prevents writability in etc
    @return the main admin page
    """
    #FIXME: correct function when removing migration kit
    from invenio.bibformat_migration_kit_assistant_lib import save_status, use_old_bibformat  #FIXME: remove when removing migration_kit
    
    #Save the status (Use or not old BibFormat)
    if not warnings:
        if version == "new": 
            save_status("use old BibFormat", status="NO")
        elif version == "old":
            save_status("use old BibFormat", status="YES")
    else:
        if version != "":
            warnings.append(('WRN_BIBFORMAT_CANNOT_EXECUTE_REQUEST'))
        warnings = get_msgs_for_code_list(warnings, 'warning', ln)
        warnings = [x[1] for x in warnings] # Get only message, not code
    #Read status to display in the web interface
    use_old_bibformat  = use_old_bibformat()
    
    return bibformat_templates.tmpl_admin_index(use_old_bibformat, ln, warnings)


def perform_request_format_templates_management(ln=cdslang, checking=0):
    """
    Returns the main management console for format templates
    
    @param ln language
    @param checking the level of checking (0: basic, 1:extensive (time consuming) )
    @return the main page for format templates management
    """

    
    #Reload in case a format was changed
    bibformat_engine.clear_caches()
    
    #get formats lists of attributes
    formats = bibformat_engine.get_format_templates(with_attributes=True)
    formats_attrs = []
    for filename in formats:
        attrs = formats[filename]['attrs']
        attrs['filename'] = filename
        attrs['editable'] = can_write_format_template(filename)
        path = templates_path + os.sep + filename
        attrs['last_mod_date'] = time.ctime(os.stat(path)[stat.ST_MTIME])
        status = check_format_template(filename, checking)
        if len(status) > 1 or (len(status)==1 and status[0][0] != 'ERR_BIBFORMAT_CANNOT_READ_TEMPLATE_FILE'):
            status = '''
            <a style="color: rgb(255, 0, 0);"
            href="%(weburl)s/admin/bibformat/bibformatadmin.py/validate_format?ln=%(ln)s&amp;bft=%(bft)s">Not OK</a>
            ''' % {'weburl':weburl,
                   'ln':ln,
                   'bft':filename}
        else:
            status = '<span style="color: rgb(0, 255, 0);">OK</span>'
        attrs['status'] = status
        formats_attrs.append(attrs)
        
    def sort_by_attr(seq):
        intermed = [ (x['name'], i, x) for i, x in enumerate(seq)]
        intermed.sort()
        return [x[-1] for x in intermed]
        
    sorted_format_templates = sort_by_attr(formats_attrs)
    
    return bibformat_templates.tmpl_admin_format_templates_management(ln, sorted_format_templates)

def perform_request_format_template_show(bft, ln=cdslang, code=None,
                                         ln_for_preview=cdslang, pattern_for_preview="",
                                         content_type_for_preview="text/html"):
    """
    Returns the editor for format templates.

    @param ln language
    @param bft the template to edit
    @param code, the code being edited
    @param ln_for_preview the language for the preview (for bfo)
    @param pattern_for_preview the search pattern to be used for the preview (for bfo)
    @return the main page for formats management
    """
    format_template = bibformat_engine.get_format_template(filename=bft, with_attributes=True)

    #Either use code being edited, or the original code inside template
    if code == None:
        code = format_template['code'].replace('%%','%') #.replace("<","&lt;").replace(">","/&gt;").replace("&","&amp;")

    #Build a default pattern if it is empty
    if pattern_for_preview == "":
        recIDs = perform_request_search()
        if len(recIDs) > 0:
            recID = recIDs[0]
            pattern_for_preview = "recid:%s" % recID

    editable = can_write_format_template(bft)

    #Look for all existing content_types
    content_types = bibformat_dblayer.get_existing_content_types()
    
    return bibformat_templates.tmpl_admin_format_template_show(ln, format_template['attrs']['name'],
                                                               format_template['attrs']['description'],
                                                               code, bft,
                                                               ln_for_preview=ln_for_preview,
                                                               pattern_for_preview=pattern_for_preview,
                                                               editable=editable,
                                                               content_type_for_preview=content_type_for_preview,
                                                               content_types=content_types)

def perform_request_format_template_show_dependencies(bft, ln=cdslang):
    """
    Show the dependencies (on elements) of the given format.
    
    @param ln language
    @param bft the filename of the template to show
    """
    format_template = bibformat_engine.get_format_template(filename=bft, with_attributes=True)
    name = format_template['attrs']['name']
    output_formats = get_outputs_that_use_template(bft)
    format_elements = get_elements_used_by_template(bft)
    tags = []
    for output_format in output_formats:
        for tag in output_format['tags']:
            tags.append(tag)
    for format_element in format_elements:
        for tag in format_element['tags']:
            tags.append(tag)            

    tags.sort()
    return bibformat_templates.tmpl_admin_format_template_show_dependencies(ln,
                                                                            name,
                                                                            bft,
                                                                            output_formats,
                                                                            format_elements,
                                                                            tags)
    
def perform_request_format_template_show_attributes(bft, ln=cdslang):
    """
    Page for template name and descrition attributes edition.
    
    @param ln language
    @param bft the template to edit
    @return the main page for format templates attributes edition
    """
    format_template = bibformat_engine.get_format_template(filename=bft, with_attributes=True)
    name = format_template['attrs']['name']
    description = format_template['attrs']['description']
    editable = can_write_format_template(bft)
    
    return bibformat_templates.tmpl_admin_format_template_show_attributes(ln,
                                                                          name,
                                                                          description,
                                                                          bft,
                                                                          editable)

   
def perform_request_format_template_show_short_doc(ln=cdslang, search_doc_pattern=""):
    """
    Returns the format elements documentation to be included inside format templated editor.

    Keep only elements that have 'search_doc_pattern' text inside description,
    if pattern not empty

    @param ln language
    @param search_doc_pattern a search pattern that specified which elements to display
    @return a brief version of the format element documentation
    """
    #get format elements lists of attributes
    elements = bibformat_engine.get_format_elements(with_built_in_params=True)

    keys =  elements.keys()
    keys.sort()
    elements = map(elements.get, keys) 

    def filter_elem(element):
        "Keep element if is string representation contains all keywords of search_doc_pattern"
        text = str(element).upper() #Basic text representation
        if search_doc_pattern != "":
            for word in search_doc_pattern.split():
                if word.upper() != "AND" and text.find(word.upper()) == -1:
                    return False
                    
        return True
    
    elements = filter(filter_elem, elements)

  
        
    return bibformat_templates.tmpl_admin_format_template_show_short_doc(ln, elements)

def perform_request_format_elements_documentation(ln=cdslang):
    """
    Returns the main management console for format elements.

    Includes list of format elements and associated administration tools.
    @param ln language
    @return the main page for format elements management
    """
    #get format elements lists of attributes
    elements = bibformat_engine.get_format_elements(with_built_in_params=True)
    
    keys =  elements.keys()
    keys.sort()
    elements = map(elements.get, keys) 
        
    return bibformat_templates.tmpl_admin_format_elements_documentation(ln, elements)

def perform_request_format_element_show_dependencies(bfe, ln=cdslang):
    """
    Show the dependencies of the given format.

    @param ln language
    @param bfe the filename of the format element to show
    """
    format_templates = get_templates_that_use_element(bfe)
    tags = get_tags_used_by_element(bfe)
    
    return bibformat_templates.tmpl_admin_format_element_show_dependencies(ln,
                                                                           bfe,
                                                                           format_templates,
                                                                           tags)

def perform_request_format_element_test(bfe, ln=cdslang, param_values=None, uid=None):
    """
    Show the dependencies of the given format.

    'param_values' is the list of values to pass to 'format'
    function of the element as parameters, in the order ...
    If params is None, this means that they have not be defined by user yet.
    
    @param ln language
    @param bfe the name of the format element to show
    @param params the list of parameters to pass to element format function
    @param uid the user id for this request
    """
    _ = gettext_set_language(ln)
    format_element = bibformat_engine.get_format_element(bfe, with_built_in_params=True)

    #Load parameter names and description
    ##
    param_names = []
    param_descriptions = []
    
    #First value is a search pattern to choose the record
    param_names.append(_("Test with record:")) # Caution: keep in sync with same text below
    param_descriptions.append(_("Enter a search query here."))
    
    #Parameters defined in this element
    for param in format_element['attrs']['params']:
        param_names.append(param['name'])
        param_descriptions.append(param['description'])

    #Parameters common to all elements of a kind
    for param in format_element['attrs']['builtin_params']:
        param_names.append(param['name'])
        param_descriptions.append(param['description'])
        
    #Load parameters values
    ##
    
    if param_values == None: #First time the page is loaded
        param_values = []

        #Propose an existing record id by default
        recIDs = perform_request_search()
        if len(recIDs) > 0:
            recID = recIDs[0]
            param_values.append("recid:%s" % recID)
        
        #Default values defined in this element
        for param in format_element['attrs']['params']:
            param_values.append(param['default'])

        #Parameters common to all elements of a kind
        for param in format_element['attrs']['builtin_params']:
            param_values.append(param['default'])


    #Execute element with parameters
    ##
    params = dict(zip(param_names, param_values))

    #Find a record corresponding to search pattern
    search_pattern = params[_("Test with record:")] # Caution keep in sync with same text above and below
    recIDs = perform_request_search(p=search_pattern)
    del params[_("Test with record:")] # Caution keep in sync with same text above
    
    if len(recIDs) > 0:
        bfo = bibformat_engine.BibFormatObject(recIDs[0], ln, search_pattern, None, uid)
        (result, errors) = bibformat_engine.eval_format_element(format_element, bfo, params)
    else:
        result = get_msgs_for_code_list([("ERR_BIBFORMAT_NO_RECORD_FOUND_FOR_PATTERN", search_pattern)],
                                        file='error', ln=cdslang)[0][1]

    return bibformat_templates.tmpl_admin_format_element_test(ln,
                                                              bfe,
                                                              format_element['attrs']['description'],
                                                              param_names,
                                                              param_values,
                                                              param_descriptions,
                                                              result)

def perform_request_output_formats_management(ln=cdslang, sortby="code"):
    """
    Returns the main management console for output formats.

    Includes list of output formats and associated administration tools.
    @param ln language
    @param sortby the sorting crieteria (can be 'code' or 'name')
    @return the main page for output formats management
    """
    #Reload in case a format was changed
    bibformat_engine.clear_caches()
    
    #get output formats lists of attributes
    output_formats_list = bibformat_engine.get_output_formats(with_attributes=True)
    output_formats = {}
    for filename in output_formats_list:
        output_format = output_formats_list[filename]
        code = output_format['attrs']['code']
        path = outputs_path + os.sep + filename
        output_format['editable'] = can_write_output_format(code)
        output_format['last_mod_date'] = time.ctime(os.stat(path)[stat.ST_MTIME])
        status = check_output_format(code)
        if len(status) > 1 or (len(status)==1 and status[0][0] != 'ERR_BIBFORMAT_CANNOT_WRITE_OUTPUT_FILE'):
            status = '''
            <a style="color: rgb(255, 0, 0);"
            href="%(weburl)s/admin/bibformat/bibformatadmin.py/validate_format?ln=%(ln)s&bfo=%(bfo)s">Not OK</a>
            ''' % {'weburl':weburl,
                   'ln':ln,
                   'bfo':code}
        else:
            status = '<span style="color: rgb(0, 255, 0);">OK</span>'
        output_format['status'] = status
        output_formats[filename] = output_format
        
    #sort according to code or name, inspired from Python Cookbook
    def get_attr(dic, attr):
        if attr == "code":
            return dic['attrs']['code']
        else:
            return dic['attrs']['names']['generic']
        
    def sort_by_attr(seq, attr):
        intermed = [ (get_attr(x, attr), i, x) for i, x in enumerate(seq)]
        intermed.sort()
        return [x[-1] for x in intermed]

    if sortby != "code" and sortby != "name":
        sortby = "code"
        
    sorted_output_formats = sort_by_attr(output_formats.values(), sortby)

    return bibformat_templates.tmpl_admin_output_formats_management(ln, sorted_output_formats)

def perform_request_output_format_show(bfo, ln=cdslang, r_fld=[], r_val=[], r_tpl=[], default="", r_upd="", args={}):
    """
    Returns the editing tools for a given output format.

    The page either shows the output format from file, or from user's
    POST session, as we want to let him edit the rules without
    saving. Policy is: r_fld, r_val, rules_tpl are list of attributes
    of the rules.  If they are empty, load from file. Else use
    POST. The i th value of each list is one of the attributes of rule
    i. Rule i is the i th rule in order of evaluation.  All list have
    the same number of item.

    r_upd contains an action that has to be performed on rules. It
    can composed of a number (i, the rule we want to modify) and an
    operator : "save" to save the rules, "add" or "del".
    syntax: operator [number]
    For eg: r_upd = _("Save Changes") saves all rules (no int should be specified).
    For eg: r_upd = _("Add New Rule") adds a rule (no int should be specified).
    For eg: r_upd = _("Remove Rule") + " 5"  deletes rule at position 5.
    The number is used only for operation delete.

    An action can also be in **args. We must look there for string starting
    with '(+|-) [number]' to increase (+) or decrease (-) a rule given by its
    index (number).
    For example "+ 5" increase priority of rule 5 (put it at fourth position).
    The string in **args can be followed by some garbage that looks like .x
    or .y, as this is returned as the coordinate of the click on the
    <input type="image">. We HAVE to use args and reason on its keys, because for <input> of
    type image, iexplorer does not return the value of the tag, but only the name.

    Action is executed only if we are working from user's POST session
    (means we must have loaded the output format first, which is
    totally normal and expected behaviour)

    IMPORTANT: we display rules evaluation index starting at 1 in
    interface, but we start internally at 0
        
    @param ln language
    @param bfo the filename of the output format to show
    @param r_fld the list of 'field' attribute for each rule
    @param r_val the list of 'value' attribute for each rule
    @param r_tpl the list of 'template' attribute for each rule
    @param default the default format template used by this output format
    @param r_upd the rule that we want to increase/decrease in order of evaluation
    """

    output_format = bibformat_engine.get_output_format(bfo, with_attributes=True)    
    format_templates =  bibformat_engine.get_format_templates(with_attributes=True)
    name = output_format['attrs']['names']['generic']
    rules = []
    debug = ""
    if len(r_fld) == 0 and r_upd=="":
        #Retrieve rules from file
        rules = output_format['rules']
        default = output_format['default']
    else:
        #Retrieve rules from given lists

        #Transform a single rule (not considered as a list with length
        #1 by the templating system) into a list
        if not isinstance(r_fld, list):
            r_fld = [r_fld]
            r_val = [r_val]
            r_tpl = [r_tpl]
             
        for i in range(len(r_fld)):
            rule = {'field': r_fld[i],
                    'value': r_val[i],
                    'template': r_tpl[i]}
            rules.append(rule)
        #Execute action
        _ = gettext_set_language(ln)
        if r_upd.startswith(_("Remove Rule")):
            #Remove rule
            index = int(r_upd.split(" ")[-1]) -1 
            del rules[index]
        elif r_upd.startswith(_("Save Changes")):
            #Save
            update_output_format_rules(bfo, rules, default)
        elif r_upd.startswith(_("Add New Rule")):
            #Add new rule
            rule = {'field': "",
                    'value': "",
                    'template': ""}
            rules.append(rule)
        else:
            #Get the action in 'args'
            #The action must be constructed from string of the kind:
            # + 5  or  - 4  or + 5.x  or -4.y
            for button_val in args.keys():#for all elements of form not handled yet
                action = button_val.split(" ")
                if action[0] == '-' or action[0] == '+':
                    index = int(action[1].split(".")[0]) -1
                    if action[0] == '-':
                        #Decrease priority
                        rule = rules[index]
                        del rules[index]
                        rules.insert(index + 1, rule)
                        #debug = 'Decrease rule '+ str(index)
                        break
                    elif action[0] == '+':
                        #Increase priority
                        rule = rules[index]
                        del rules[index]
                        rules.insert(index - 1, rule)
                        #debug = 'Increase rule ' + str(index)
                        break


    editable = can_write_output_format(bfo)

    return bibformat_templates.tmpl_admin_output_format_show(ln,
                                                            bfo,
                                                            name,
                                                            rules,
                                                            default,
                                                            format_templates,
                                                            editable)

def perform_request_output_format_show_dependencies(bfo, ln=cdslang):
    """
    Show the dependencies of the given format.
    
    @param ln language
    @param bfo the filename of the output format to show
    """
    output_format = bibformat_engine.get_output_format(code=bfo, with_attributes=True)
    name = output_format['attrs']['names']['generic']
    format_templates = get_templates_used_by_output(bfo)
    
    return bibformat_templates.tmpl_admin_output_format_show_dependencies(ln,
                                                                          name,
                                                                          bfo,
                                                                          format_templates)
    
def perform_request_output_format_show_attributes(bfo, ln=cdslang):
    """
    Page for output format names and description attributes edition.
    
    @param ln language
    @param bfo filename of output format to edit
    @return the main page for output format attributes edition
    """
    output_format = bibformat_engine.get_output_format(code=bfo, with_attributes=True)

    name = output_format['attrs']['names']['generic']
    description = output_format['attrs']['description']
    content_type = output_format['attrs']['content_type']
    #Get translated names. Limit to long names now.
    #Translation are given in order of languages in language_list_long()
    names_trans = []
    for lang in language_list_long():
        name_trans = output_format['attrs']['names']['ln'].get(lang[0], "")
        names_trans.append({'lang':lang[1], 'trans':name_trans})

    editable = can_write_output_format(bfo)
    
    return bibformat_templates.tmpl_admin_output_format_show_attributes(ln,
                                                                        name,
                                                                        description,
                                                                        content_type,
                                                                        bfo,
                                                                        names_trans,
                                                                        editable)


def perform_request_knowledge_bases_management(ln=cdslang):
    """
    Returns the main page for knowledge bases management.
    
    @param ln language
    @return the main page for knowledge bases management
    """
    kbs = bibformat_dblayer.get_kbs()
    
    return bibformat_templates.tmpl_admin_kbs_management(ln, kbs)

def perform_request_knowledge_base_show(kb_id, ln=cdslang, sortby="to"):
    """
    Show the content of a knowledge base
    
    @param ln language
    @param kb a knowledge base id
    @param sortby the sorting criteria ('from' or 'to')
    @return the content of the given knowledge base
    """
    name = bibformat_dblayer.get_kb_name(kb_id)
    mappings = bibformat_dblayer.get_kb_mappings(name, sortby)
    
    return bibformat_templates.tmpl_admin_kb_show(ln, kb_id, name, mappings, sortby)


def perform_request_knowledge_base_show_attributes(kb_id, ln=cdslang, sortby="to"):
    """
    Show the attributes of a knowledge base
    
    @param ln language
    @param kb a knowledge base id
    @param sortby the sorting criteria ('from' or 'to')
    @return the content of the given knowledge base
    """
    name = bibformat_dblayer.get_kb_name(kb_id)
    description = bibformat_dblayer.get_kb_description(name)
    
    return bibformat_templates.tmpl_admin_kb_show_attributes(ln, kb_id, name, description, sortby)


def perform_request_knowledge_base_show_dependencies(kb_id, ln=cdslang, sortby="to"):
    """
    Show the dependencies of a kb
    
    @param ln language
    @param kb a knowledge base id
    @param sortby the sorting criteria ('from' or 'to')
    @return the dependencies of the given knowledge base
    """
    name = bibformat_dblayer.get_kb_name(kb_id)
    format_elements = get_elements_that_use_kb(name)
    
    return bibformat_templates.tmpl_admin_kb_show_dependencies(ln, kb_id, name, sortby, format_elements)

def add_format_template():
    """
    Adds a new format template (mainly create file with unique name)

    @return the filename of the created format
    """
    (filename, name) = bibformat_engine.get_fresh_format_template_filename("Untitled")
    
    out = '<name>%(name)s</name><description></description>' % {'name':name}
    path = templates_path + os.sep + filename
    format = open(path, 'w')
    format.write(out)
    format.close

    return filename

def delete_format_template(filename):
    """
    Delete a format template given by its filename

    If format template is not writable, do not remove

    @param filename the format template filename
    """
    if not can_write_format_template(filename):
        return
    
    path = templates_path + os.sep + filename
    os.remove(path)
    bibformat_engine.clear_caches()
    
def update_format_template_code(filename, code=""):
    """
    Saves code inside template given by filename
    """
    format_template = bibformat_engine.get_format_template_attrs(filename)
    name = format_template['name']
    description = format_template['description']
    
    out = '''
<name>%(name)s</name>
<description>%(description)s</description>
%(code)s
    ''' % {'name':name, 'description':description, 'code':code}
    path = templates_path + os.sep + filename
    format = open(path, 'w')
    format.write(out)
    format.close
    
    bibformat_engine.clear_caches()
    
def update_format_template_attributes(filename, name="", description=""):
    """
    Saves name and description inside template given by filename.

    the filename must change according to name, and every output format
    having reference to filename must be updated.

    If name already exist, use fresh filename (we never overwrite other templates) amd
    remove old one.

    @return the filename of the modified format
    """
    format_template = bibformat_engine.get_format_template(filename, with_attributes=True)
    code = format_template['code']
    if format_template['attrs']['name'] != name:
        #name has changed, so update filename
        old_filename = filename
        old_path = templates_path + os.sep + old_filename
        #Remove old one
        os.remove(old_path)
        
        (filename, name) = bibformat_engine.get_fresh_format_template_filename(name)

        #Change output formats that calls this template
        output_formats = bibformat_engine.get_output_formats()

        for output_format_filename in output_formats:
            if can_read_output_format(output_format_filename) and can_write_output_format(output_format_filename):
                output_path = outputs_path + os.sep + output_format_filename
                format = open(output_path, 'r')
                output_text = format.read()
                format.close
                output_pattern = re.compile("---(\s)*" + old_filename, re.IGNORECASE)
                mod_output_text = output_pattern.sub("--- " + filename, output_text)
                if output_text != mod_output_text:
                    format = open(output_path, 'w')
                    format.write(mod_output_text)
                    format.close

    #Write updated format template
    out = '''<name>%(name)s</name><description>%(description)s</description>%(code)s''' % {'name':name,
                                                                                           'description':description,
                                                                                           'code':code}

    path = templates_path + os.sep + filename
    format = open(path, 'w')
    format.write(out)
    format.close

    bibformat_engine.clear_caches()

    return filename

def add_output_format():
    """
    Adds a new output format (mainly create file with unique name)

    @return the code of the created format
    """
    (filename, code) = bibformat_engine.get_fresh_output_format_filename("UNTLD")
    
    #Add entry in database
    bibformat_dblayer.add_output_format(code)
    bibformat_dblayer.set_output_format_name(code, "Untitled", lang="generic")
    bibformat_dblayer.set_output_format_content_type(code, "text/html")
    
    #Add file 
    out = ""
    path = outputs_path + os.sep + filename
    format = open(path, 'w')
    format.write(out)
    format.close

    return code

def delete_output_format(code):
    """
    Delete a format template given by its code

    if file is not writable, don't remove

    @param code the 6 letters code of the output format to remove
    """
    if not can_write_output_format(code):
        return
        
    #Remove entry from database
    bibformat_dblayer.remove_output_format(code)

    #Remove file
    filename = bibformat_engine.resolve_output_format_filename(code)
    path = outputs_path + os.sep + filename
    os.remove(path)

    bibformat_engine.clear_caches()
    
    
def update_output_format_rules(code, rules=[], default=""):
    """
    Saves rules inside output format given by code
    """

    #Generate output format syntax
    #Try to group rules by field
    previous_field = ""
    out = ""
    for rule in rules:
        field = rule["field"]
        value = rule["value"]
        template = rule["template"]
        if previous_field != field:
            out += "tag %s:\n" % field

        out +="%(value)s --- %(template)s\n" % {'value':value, 'template':template}
        previous_field = field

    out += "default: %s" % default
    filename = bibformat_engine.resolve_output_format_filename(code)
    path = outputs_path + os.sep + filename
    format = open(path, 'w')
    format.write(out)
    format.close

    bibformat_engine.clear_caches()

def update_output_format_attributes(code, name="", description="", new_code="", content_type="", names_trans=[]):
    """
    Saves name and description inside output format given by filename.

    If new_code already exist, use fresh code (we never overwrite other output).

    @param description the new description
    @param name the new name
    @param code the new short code (== new bfo) of the output format
    @param code the code of the output format to update
    @param names_trans the translations in the same order as the languages from get_languages()
    @param content_type the new content_type of the output format
    @return the filename of the modified format
    """
    
    bibformat_dblayer.set_output_format_description(code, description)
    bibformat_dblayer.set_output_format_content_type(code, content_type)
    bibformat_dblayer.set_output_format_name(code, name, lang="generic")
    i = 0
    for lang in language_list_long():
        if names_trans[i] != "":
            bibformat_dblayer.set_output_format_name(code, names_trans[i], lang[0])
        i += 1

    new_code = new_code.upper()
    if code != new_code:
        #If code has changed, we must update filename with a new unique code
        old_filename = bibformat_engine.resolve_output_format_filename(code)
        old_path = outputs_path + os.sep + old_filename
        (new_filename, new_code) = bibformat_engine.get_fresh_output_format_filename(new_code)
        new_path = outputs_path + os.sep + new_filename
        os.rename(old_path, new_path)
        bibformat_dblayer.change_output_format_code(code, new_code)    
    
    bibformat_engine.clear_caches()

    return new_code
    
def add_kb_mapping(kb_name, key, value=""):
    """
    Adds a new mapping to given kb

    @param kb_name the name of the kb where to insert the new value
    @param key the key of the mapping
    @param value the value of the mapping
    """
    bibformat_dblayer.add_kb_mapping(kb_name, key, value)

def remove_kb_mapping(kb_name, key):
    """
    Delete an existing kb mapping in kb
    
    @param kb_name the name of the kb where to insert the new value
    @param key the key of the mapping
    """
    bibformat_dblayer.remove_kb_mapping(kb_name, key)

def update_kb_mapping(kb_name, old_key, key, value):
    """
    Update an existing kb mapping with key old_key with a new key and value
    
    @param kb_name the name of the kb where to insert the new value
    @param the key of the mapping in the kb
    @param key the new key of the mapping
    @param value the new value of the mapping
    """
    bibformat_dblayer.update_kb_mapping(kb_name, old_key, key, value)

def get_kb_name(kb_id):
    """
    Returns the name of the kb given by id
    """
    return bibformat_dblayer.get_kb_name(kb_id)

def update_kb_attributes(kb_name, new_name, new_description):
    """
    Updates given kb_name with a new name and new description

    @param kb_name the name of the kb to update
    @param new_name the new name for the kb
    @param new_description the new description for the kb
    """
    bibformat_dblayer.update_kb(kb_name, new_name, new_description)

def add_kb(kb_name="Untitled"):
    """
    Adds a new kb in database, and returns its id
    The name of the kb will be 'Untitled#'
    such that it is unique.

    @param kb_name the name of the kb
    @return the id of the newly created kb
    """
    name = kb_name
    i = 1
    while bibformat_dblayer.kb_exists(name):
        name = kb_name + " " + str(i)
        i += 1
        
    kb_id = bibformat_dblayer.add_kb(name, "")

    return kb_id

def delete_kb(kb_name):
    """
    Deletes given kb from database
    """
    bibformat_dblayer.delete_kb(kb_name)

def can_read_format_template(filename):
    """
    Returns 0 if we have read permission on given format template, else
    returns other integer
    """
    path = "%s%s%s" % (templates_path, os.sep, filename)
    return os.access(path, os.R_OK)
   
def can_read_output_format(bfo):
    """
    Returns 0 if we have read permission on given output format, else
    returns other integer
    """
    filename = bibformat_engine.resolve_output_format_filename(bfo)
    path = "%s%s%s" % (outputs_path, os.sep, filename)
    return os.access(path, os.R_OK)
    
def can_read_format_element(name):
    """
    Returns 0 if we have read permission on given format element, else
    returns other integer
    """

    filename = bibformat_engine.resolve_format_element_filename(name)
    path = "%s%s%s" % (elements_path, os.sep, filename)
    return os.access(path, os.R_OK)
    
def can_write_format_template(bft):
    """
    Returns 0 if we have write permission on given format template, else
    returns other integer
    """
    if not can_read_format_template(bft):
        return False

    path = "%s%s%s" % (templates_path, os.sep, bft)
    return os.access(path, os.W_OK)

def can_write_output_format(bfo):
    """
    Returns 0 if we have write permission on given output format, else
    returns other integer
    """
    if not can_read_output_format(bfo):
        return False
    
    filename = bibformat_engine.resolve_output_format_filename(bfo)
    path = "%s%s%s" % (outputs_path, os.sep, filename)
    return os.access(path, os.W_OK)

def can_write_etc_bibformat_dir():
    """
    Returns true if we can write in etc/bibformat dir.
    """
    path = "%s%sbibformat" % (etcdir, os.sep)
    return os.access(path, os.W_OK)
       
def get_outputs_that_use_template(filename):
    """
    Returns a list of output formats that call the given format template.
    The returned output formats also give their dependencies on tags.
    
    We don't return the complete output formats but some reference to
    them (filename + names)

    [ {'filename':"filename_1.bfo"
       'names': {'en':"a name", 'fr': "un nom", 'generic':"a name"}
       'tags': ['710__a', '920__']
      },
      ...
    ]

    Returns output formats references sorted by (generic) name

    @param filename a format template filename
    """
    output_formats_list = {}
    tags = []
    output_formats = bibformat_engine.get_output_formats(with_attributes=True)
    for output_format in output_formats:
        name = output_formats[output_format]['attrs']['names']['generic']
        #First look at default template, and add it if necessary
        if output_formats[output_format]['default'] == filename:
            output_formats_list[name] = {'filename':output_format,
                                         'names':output_formats[output_format]['attrs']['names'],
                                         'tags':[]}
        #Second look at each rule
        found = False
        for rule in output_formats[output_format]['rules']:
            if rule['template'] == filename:
                found = True
                tags.append(rule['field']) #Also build dependencies on tags

        #Finally add dependency on template from rule (overwrite default dependency,
        #which is weaker in term of tag)
        if found == True:
            output_formats_list[name] = {'filename':output_format,
                                         'names':output_formats[output_format]['attrs']['names'],
                                         'tags':tags}
            


    keys = output_formats_list.keys()
    keys.sort()
    return map(output_formats_list.get, keys)        

def get_elements_used_by_template(filename):
    """
    Returns a list of format elements that are called by the given format template.
    The returned elements also give their dependencies on tags

    The list is returned sorted by name

    [ {'filename':"filename_1.py"
       'name':"filename_1"
       'tags': ['710__a', '920__']
      },
      ...
    ]

    Returns elements sorted by name

    @param filename a format template filename
    """
    format_elements = {}
    format_template = bibformat_engine.get_format_template(filename=filename, with_attributes=True)
    code = format_template['code']
    format_elements_iter = bibformat_engine.pattern_tag.finditer(code)
    for result in format_elements_iter:
        function_name = result.group("function_name").lower()
        if function_name != None and not format_elements.has_key(function_name):
            filename = bibformat_engine.resolve_format_element_filename("BFE_"+function_name)
            if filename != None:
                tags = get_tags_used_by_element(filename)
                format_elements[function_name] = {'name':function_name.lower(),
                                                  'filename':filename,
                                                  'tags':tags}

    keys = format_elements.keys()
    keys.sort()
    return map(format_elements.get, keys)


# Format Elements Dependencies
##

def get_tags_used_by_element(filename):
    """
    Returns a list of tags used by given format element

    APPROXIMATIVE RESULTS: the tag are retrieved in field(), fields()
    and control_field() function. If they are used computed, or saved
    in a variable somewhere else, they are not retrieved
    @TODO: There is room for improvements. For example catch call
    to BibRecord functions, or use of <BFE_FIELD tag=""/>

    Returns tags sorted by value
    
    @param filename a format element filename  
    """
    tags = {}

    format_element = bibformat_engine.get_format_element(filename)
    if format_element == None:
        return []
    elif format_element['type']=="field":
        tags = format_element['attrs']['tags']
        return tags
        
    filename = bibformat_engine.resolve_format_element_filename(filename)
    path = elements_path + os.sep + filename
    format = open(path, 'r')
    code = format.read()
    format.close
    tags_pattern = re.compile('''
    (field|fields|control_field)\s*       #Function call
    \(\s*                                 #Opening parenthesis
    [\'"]+                                #Single or double quote
    (?P<tag>.+?)                          #Tag
    [\'"]+\s*                             #Single or double quote
    \)                                    #Closing parenthesis
     ''', re.VERBOSE | re.MULTILINE)
    
    tags_iter = tags_pattern.finditer(code)
    for result in tags_iter:
        tags[result.group("tag")] = result.group("tag")

    return tags.values()

def get_templates_that_use_element(name):
    """
    Returns a list of format templates that call the given format element.
    The returned format templates also give their dependencies on tags.

    [ {'filename':"filename_1.bft"
       'name': "a name"
       'tags': ['710__a', '920__']
      },
      ...
    ]

    Returns templates sorted by name
    
    @param name a format element name
    """
    format_templates = {}
    tags = []
    files = os.listdir(templates_path) #Retrieve all templates
    for file in files:
        if file.endswith(format_template_extension):
            format_elements = get_elements_used_by_template(file) #Look for elements used in template
            format_elements = map(lambda x: x['name'].lower(), format_elements)
            try: #Look for element
                format_elements.index(name.lower()) #If not found, get out of "try" statement
                
                format_template = bibformat_engine.get_format_template(filename=file, with_attributes=True)
                template_name = format_template['attrs']['name']
                format_templates[template_name] = {'name':template_name,
                                                   'filename':file}
            except:
                print name+" not found in "+str(format_elements)
                pass
            
    keys = format_templates.keys()
    keys.sort()
    return map(format_templates.get, keys)  

# Output Formats Dependencies
##

def get_templates_used_by_output(code):
    """
    Returns a list of templates used inside an output format give by its code
    The returned format templates also give their dependencies on elements and tags

    [ {'filename':"filename_1.bft"
       'name': "a name"
       'elements': [{'filename':"filename_1.py", 'name':"filename_1", 'tags': ['710__a', '920__']
      }, ...]
      },
      ...
    ]

    Returns templates sorted by name
    
    """
    format_templates = {}
    output_format = bibformat_engine.get_output_format(code, with_attributes=True)

    filenames = map(lambda x: x['template'], output_format['rules'])
    if output_format['default'] != "":
        filenames.append(output_format['default'])
        
    for filename in filenames:
        template = bibformat_engine.get_format_template(filename, with_attributes=True)
        name = template['attrs']['name']
        elements = get_elements_used_by_template(filename)
        format_templates[name] = {'name':name,
                                  'filename':filename,
                                  'elements':elements}


    keys = format_templates.keys()
    keys.sort()
    return map(format_templates.get, keys)  


# Knowledge Bases Dependencies
##

def get_elements_that_use_kb(name):
    """
    Returns a list of elements that call given kb

    [ {'filename':"filename_1.py"
       'name': "a name"
      },
      ...
    ]
    
    Returns elements sorted by name
    """

    format_elements = {}
    files = os.listdir(elements_path) #Retrieve all elements in files
    for filename in files:
        if filename.endswith(".py"):
            path = elements_path + os.sep + filename
            format = open(path, 'r')
            code = format.read()
            format.close
            #Search for use of kb inside code
            kb_pattern = re.compile('''
            (bfo.kb)\s*                #Function call
            \(\s*                      #Opening parenthesis
            [\'"]+                     #Single or double quote
            (?P<kb>%s)                 #kb
            [\'"]+\s*                  #Single or double quote
            ,                          #comma
            ''' % name, re.VERBOSE | re.MULTILINE | re.IGNORECASE)
    
            result = kb_pattern.search(code)
            if result != None:
                name = ("".join(filename.split(".")[:-1])).lower()
                if name.startswith("bfe_"):
                    name = name[4:]
                format_elements[name] = {'filename':filename, 'name': name}
            
       
    keys = format_elements.keys()
    keys.sort()
    return map(format_elements.get, keys)  

# Validation tools
##

def perform_request_format_validate(ln=cdslang, bfo=None, bft=None, bfe=None):
    """
    Returns a page showing the status of an output format or format
    template or format element. This page is called from output
    formats management page or format template management page or
    format elements documentation.

    The page only shows the status of one of the format, depending on
    the specified one. If multiple are specified, shows the first one.

    @param ln language
    @param bfo an output format 6 chars code
    @param bft a format element filename
    @param bfe a format element name
    """

    if bfo != None:
        errors = check_output_format(bfo)
        messages = get_msgs_for_code_list(code_list = errors, ln=ln)
    elif bft != None:
        errors = check_format_template(bft, checking=1)
        messages = get_msgs_for_code_list(code_list = errors, ln=ln)
    elif bfe != None:
        errors = check_format_element(bfe)
        messages = get_msgs_for_code_list(code_list = errors, ln=ln)

    if messages == None:
        messages = []

    messages = map(lambda x: encode_for_xml(x[1]), messages)
    
    return bibformat_templates.tmpl_admin_validate_format(ln, messages)
                                                                         
    
def check_output_format(code):
    """
    Returns the list of errors in the output format given by code

    The errors are the formatted errors defined in bibformat_config.py file.

    @param code the 6 chars code of the output format to check
    @return a list of errors
    """
    errors = []
    filename = bibformat_engine.resolve_output_format_filename(code)
    if can_read_output_format(code):
        path = outputs_path + os.sep + filename
        format = open(path)
        current_tag = ''
        i = 0
        for line in format:
            i += 1
            if line.strip() == "":
                #ignore blank lines
                continue
            clean_line = line.rstrip("\n\r ") #remove spaces and eol
            if line.strip().endswith(":") or (line.strip().lower().startswith("tag") and line.find('---') == -1):
                #check tag
                if not clean_line.endswith(":"):
                    #column misses at the end of line  
                    errors.append(("ERR_BIBFORMAT_OUTPUT_RULE_FIELD_COL", line, i))
                if not clean_line.lower().startswith("tag"):
                    #tag keyword is missing
                    errors.append(("ERR_BIBFORMAT_OUTPUT_TAG_MISSING", line, i))
                elif not clean_line.startswith("tag"):
                    #tag was not lower case
                    errors.append(("ERR_BIBFORMAT_OUTPUT_WRONG_TAG_CASE", line, i))
                    
                clean_line = clean_line.rstrip(": ") #remove : and spaces at the end of line
                
                current_tag = "".join(clean_line.split()[1:]).strip() #the tag starts at second position
                if len(clean_line.split()) > 2: #We should only have 'tag' keyword and tag
                    errors.append(("ERR_BIBFORMAT_INVALID_OUTPUT_RULE_FIELD", i))  
                else:
                    if len(check_tag(current_tag)) > 0:
                        #Invalid tag
                        errors.append(("ERR_BIBFORMAT_INVALID_OUTPUT_RULE_FIELD_tag", current_tag, i))
                    if not clean_line.startswith("tag"):
                        errors.append(("ERR_BIBFORMAT_INVALID_OUTPUT_RULE_FIELD", i))

            elif line.find('---') != -1:
                #check condition
                if current_tag == "":
                    errors.append(("ERR_BIBFORMAT_OUTPUT_CONDITION_OUTSIDE_FIELD", line, i))
                    
                words = line.split('---')
                if len(words) != 2:
                    errors.append(("ERR_BIBFORMAT_INVALID_OUTPUT_CONDITION", line, i))
                template = words[-1].strip()
                path = templates_path + os.sep + template
                if not os.path.exists(path):
                    errors.append(("ERR_BIBFORMAT_WRONG_OUTPUT_RULE_TEMPLATE_REF", template, i))
                              
            elif line.find(':') != -1 or (line.strip().lower().startswith("default") and line.find('---') == -1):
                #check default template
                clean_line = line.strip()
                if line.find(':') == -1:
                    #column misses after default  
                    errors.append(("ERR_BIBFORMAT_OUTPUT_RULE_DEFAULT_COL", line, i))
                if not clean_line.startswith("default"):
                    #default keyword is missing
                    errors.append(("ERR_BIBFORMAT_OUTPUT_DEFAULT_MISSING", line, i))
                if not clean_line.startswith("default"):
                    #default was not lower case
                    errors.append(("ERR_BIBFORMAT_OUTPUT_WRONG_DEFAULT_CASE", line, i))
                default = "".join(line.split(':')[1]).strip()
                path = templates_path + os.sep + default
                if not os.path.exists(path):
                    errors.append(("ERR_BIBFORMAT_WRONG_OUTPUT_RULE_TEMPLATE_REF", default, i))
                              
            else:
                #check others
                errors.append(("ERR_BIBFORMAT_WRONG_OUTPUT_LINE", line, i))
    else:
        errors.append(("ERR_BIBFORMAT_CANNOT_READ_OUTPUT_FILE", filename, ""))
    
    return errors

def check_format_template(filename, checking=0):
    """
    Returns the list of errors in the format template given by its filename

    The errors are the formatted errors defined in bibformat_config.py file.

    @param filename the filename of the format template to check
    @param checking the level of checking (0:basic, >=1 extensive (time-consuming))
    @return a list of errors
    """
    errors = []
    if can_read_format_template(filename):#Can template be read?
        #format_template = bibformat_engine.get_format_template(filename, with_attributes=True)
        format = open("%s%s%s" % (templates_path, os.sep, filename))
        code = format.read()
        format.close()
        #Look for name
        match = bibformat_engine.pattern_format_template_name.search(code)
        if match == None:#Is tag <name> defined in template?
            errors.append(("ERR_BIBFORMAT_TEMPLATE_HAS_NO_NAME", filename))

        #Look for description
        match = bibformat_engine.pattern_format_template_desc.search(code)
        if match == None:#Is tag <description> defined in template?
            errors.append(("ERR_BIBFORMAT_TEMPLATE_HAS_NO_DESCRIPTION", filename))
        
        format_template = bibformat_engine.get_format_template(filename, with_attributes=False)
        code = format_template['code']
        #Look for calls to format elements
        #Check existence of elements and attributes used in call
        elements_call = bibformat_engine.pattern_tag.finditer(code)
        for element_match in elements_call:
            element_name = element_match.group("function_name")
            filename = bibformat_engine.resolve_format_element_filename(element_name)
            if filename == None and not bibformat_dblayer.tag_exists_for_name(element_name): #Is element defined?
                errors.append(("ERR_BIBFORMAT_TEMPLATE_CALLS_UNDEFINED_ELEM", filename, element_name))
            else:
                format_element = bibformat_engine.get_format_element(element_name, with_built_in_params=True)
                if format_element == None:#Can element be loaded?
                    if not can_read_format_element(element_name):
                        errors.append(("ERR_BIBFORMAT_TEMPLATE_CALLS_UNREADABLE_ELEM", filename, element_name))
                    else:
                        errors.append(("ERR_BIBFORMAT_TEMPLATE_CALLS_UNLOADABLE_ELEM", element_name, filename))
                else:
                    #are the parameters used defined in element?
                    params_call = bibformat_engine.pattern_function_params.finditer(element_match.group())
                    all_params = {}
                    for param_match in params_call:
                        param = param_match.group("param")
                        value = param_match.group("value")
                        all_params[param] = value
                        allowed_params = []

                        #Built-in params
                        for allowed_param in format_element['attrs']['builtin_params']:
                            allowed_params.append(allowed_param['name'])

                        #Params defined in element
                        for allowed_param in format_element['attrs']['params']:
                            allowed_params.append(allowed_param['name'])
                            
                        if not param in allowed_params:
                            errors.append(("ERR_BIBFORMAT_TEMPLATE_WRONG_ELEM_ARG",
                                           element_name, param, filename))

                    # The following code is too much time consuming. Only do where really requested
                    if checking > 0:
                        #Try to evaluate, with any object and pattern
                        recIDs = perform_request_search()
                        if len(recIDs) > 0:
                            recID = recIDs[0]
                            bfo = bibformat_engine.BibFormatObject(recID, search_pattern="Test")
                            (result, errors_) = bibformat_engine.eval_format_element(format_element, bfo, all_params, verbose=7)
                            errors.extend(errors_)
                    
    else:#Template cannot be read
        errors.append(("ERR_BIBFORMAT_CANNOT_READ_TEMPLATE_FILE", filename, ""))
    return errors

def check_format_element(name):
    """
    Returns the list of errors in the format element given by its name

    The errors are the formatted errors defined in bibformat_config.py file.

    @param name the name of the format element to check
    @return a list of errors
    """
    errors = []
    filename = bibformat_engine.resolve_format_element_filename(name)
    if filename != None:#Can element be found in files?
        if can_read_format_element(name):#Can element be read?
            #Try to load
            try:
                module_name = filename
                if module_name.endswith(".py"):
                    module_name = module_name[:-3]
                    
                module = __import__("invenio.bibformat_elements."+module_name)
                function_format  = module.bibformat_elements.__dict__[module_name].format

                #Try to evaluate, with any object and pattern
                recIDs = perform_request_search()
                if len(recIDs) > 0:
                    recID = recIDs[0]
                    bfo = bibformat_engine.BibFormatObject(recID, search_pattern="Test")
                    element = bibformat_engine.get_format_element(name)
                    (result, errors_) = bibformat_engine.eval_format_element(element, bfo, verbose=7)
                    errors.extend(errors_)
            except Exception, e:
                errors.append(("ERR_BIBFORMAT_IN_FORMAT_ELEMENT", name, e))            
        else:
            errors.append(("ERR_BIBFORMAT_CANNOT_READ_ELEMENT_FILE", filename, ""))
    elif bibformat_dblayer.tag_exists_for_name(name):#Can element be found in database?
        pass
    else:
        errors.append(("ERR_BIBFORMAT_CANNOT_RESOLVE_ELEMENT_NAME", name))

    return errors

def check_tag(tag):
    """
    Checks the validity of a tag
    """
    errors = []
    return errors

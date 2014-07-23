# -*- coding: utf-8 -*-
import os

from aiida.common.exceptions import InputValidationError
from aiida.orm import DataFactory
from aiida.common.datastructures import CalcInfo
from aiida.orm.data.upf import get_pseudos_from_structure
from aiida.common.utils import classproperty

from aiida.orm.data.structure import StructureData
from aiida.orm.data.parameter import ParameterData
from aiida.orm.data.upf import UpfData
from aiida.orm.data.remote import RemoteData 

__author__ = "Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari, and Boris Kozinsky"
__copyright__ = u"Copyright (c), 2012-2014, École Polytechnique Fédérale de Lausanne (EPFL), Laboratory of Theory and Simulation of Materials (THEOS), MXC - Station 12, 1015 Lausanne, Switzerland. All rights reserved."
__license__ = "MIT license, see LICENSE.txt file"
__version__ = "0.2.0"

class BasePwCpInputGenerator(object):

    PSEUDO_SUBFOLDER = './pseudo/'
    OUTPUT_SUBFOLDER = './out/'
    PREFIX = 'aiida'
    INPUT_FILE_NAME = 'aiida.in'
    OUTPUT_FILE_NAME = 'aiida.out'
    DATAFILE_XML_BASENAME = 'data-file.xml'
    DATAFILE_XML = 'undefined.xml'
#    DATAFILE_XML = os.path.join(OUTPUT_SUBFOLDER, 
#                               '{}.save'.format(PREFIX), 
#                               DATAFILE_XML_BASENAME)

    # Additional files that should always be retrieved for the specific plugin
    _internal_retrieve_list = []

    ## Default PW output parser provided by AiiDA
    #_default_parser = None
    ##_default_parser = 'quantumespresso.pw'
    
    _automatic_namelists = {}

    # in restarts, will not copy but use symlinks
    _default_symlink_usage = True

    # in restarts, it will copy from the parent the following 
    _restart_copy_from = os.path.join(OUTPUT_SUBFOLDER,'*')
    
    # in restarts, it will copy the previous folder in the following one 
    _restart_copy_to = OUTPUT_SUBFOLDER
    
#    _automatic_namelists = {
#        'scf':   ['CONTROL', 'SYSTEM', 'ELECTRONS'],
#        'nscf':  ['CONTROL', 'SYSTEM', 'ELECTRONS'],
#        'bands': ['CONTROL', 'SYSTEM', 'ELECTRONS'],
#        'relax': ['CONTROL', 'SYSTEM', 'ELECTRONS', 'IONS'],
#        'md':    ['CONTROL', 'SYSTEM', 'ELECTRONS', 'IONS'],
#        'vc-md':    ['CONTROL', 'SYSTEM', 'ELECTRONS', 'IONS', 'CELL'],
#        'vc-relax': ['CONTROL', 'SYSTEM', 'ELECTRONS', 'IONS', 'CELL'],
#        }


    # Keywords that cannot be set
    # If the length of the tuple is three, the third value is the value that
    # will be automatically set.
    # Note that some values (ibrav, nat, ntyp, ...) are overridden anyway
#     _blocked_keywords = [('CONTROL', 'pseudo_dir'), # set later
#          ('CONTROL', 'outdir'),  # set later
#          ('CONTROL', 'prefix'),  # set later
#          ('SYSTEM', 'ibrav'),  # set later
#          ('SYSTEM', 'celldm'),
#          ('SYSTEM', 'nat'),  # set later
#          ('SYSTEM', 'ntyp'),  # set later
#          ('SYSTEM', 'a'), ('SYSTEM', 'b'), ('SYSTEM', 'c'),
    #     ('SYSTEM', 'cosab'), ('SYSTEM', 'cosac'), ('SYSTEM', 'cosbc'),
    #]
    
    #_use_kpoints = False
    
    @classproperty
    def _baseclass_use_methods(cls):
        """
        This will be manually added to the _use_methods in each subclass
        """
        return {
            "structure": {
               'valid_types': StructureData,
               'additional_parameter': None,
               'linkname': 'structure',
               'docstring': "Choose the input structure to use",
               },
            "settings": {
               'valid_types': ParameterData,
               'additional_parameter': None,
               'linkname': 'settings',
               'docstring': "Use an additional node for special settings",
               },
            "parameters": {
               'valid_types': ParameterData,
               'additional_parameter': None,
               'linkname': 'parameters',
               'docstring': ("Use a node that specifies the input parameters "
                             "for the namelists"),
               },
            "parent_folder": {
               'valid_types': RemoteData,
               'additional_parameter': None,
               'linkname': 'parent_calc_folder',
               'docstring': ("Use a remote folder as parent folder (for "
                             "restarts and similar"),
               },
            "pseudo": {
               'valid_types': UpfData,
               'additional_parameter': "kind",
               'linkname': cls._get_linkname_pseudo,
               'docstring': ("Use a node for the UPF pseudopotential of one of "
                             "the elements in the structure. You have to pass "
                             "an additional parameter ('kind') specifying the "
                             "name of the structure kind (i.e., the name of "
                             "the species) for which you want to use this "
                             "pseudo"),
               },
            }

    
    def _prepare_for_submission(self,tempfolder,
                                    inputdict):        
        """
        This is the routine to be called when you want to create
        the input files and related stuff with a plugin.
        
        :param tempfolder: a aiida.common.folders.Folder subclass where
                           the plugin should put all its files.
        :param inputdict: a dictionary with the input nodes, as they would
                be returned by get_inputdata_dict (without the Code!)
        """
        from aiida.common.utils import get_unique_filename, get_suggestion

        local_copy_list = []
        remote_copy_list = []
        remote_symlink_list = []
        
        try:
            parameters = inputdict.pop(self.get_linkname('parameters'))
        except KeyError:
            raise InputValidationError("No parameters specified for this calculation")
        if not isinstance(parameters, ParameterData):
            raise InputValidationError("parameters is not of type ParameterData")
        
        try:
            structure = inputdict.pop(self.get_linkname('structure'))
        except KeyError:
            raise InputValidationError("No structure specified for this calculation")
        if not isinstance(structure,  StructureData):
            raise InputValidationError("structure is not of type StructureData")

        if self._use_kpoints:
            try:
                kpoints = inputdict.pop(self.get_linkname('kpoints'))
            except KeyError:
                raise InputValidationError("No kpoints specified for this calculation")
            if not isinstance(kpoints,  ParameterData):
                raise InputValidationError("kpoints is not of type ParameterData")

        # Settings can be undefined, and defaults to an empty dictionary
        settings = inputdict.pop(self.get_linkname('settings'),None)
        if settings is None:
            settings_dict = {}
        else:
            if not isinstance(settings,  ParameterData):
                raise InputValidationError("settings, if specified, must be of "
                                           "type ParameterData")
            # Settings converted to uppercase
            settings_dict = _uppercase_dict(settings.get_dict(),
                                            dict_name='settings')
        
        pseudos = {}
        for link in inputdict.keys():
            if link.startswith(self._get_linkname_pseudo_prefix()):
                kind = link[len(self._get_linkname_pseudo_prefix()):]
                pseudos[kind] = inputdict.pop(link)
                if not isinstance(pseudos[kind], UpfData):
                    raise InputValidationError("Pseudo for kind {} is not of "
                                               "type UpfData".format(kind))

        parent_calc_folder = inputdict.pop(self.get_linkname('parent_folder'),None)
        if parent_calc_folder is not None:
            if not isinstance(parent_calc_folder,  RemoteData):
                raise InputValidationError("parent_calc_folder, if specified,"
                    "must be of type RemoteData")

        # Here, there should be no more parameters...
        if inputdict:
            raise InputValidationError("The following input data nodes are "
                "unrecognized: {}".format(inputdict.keys()))

        # Check structure, get species, check peudos
        kindnames = [k.name for k in structure.kinds]
        if set(kindnames) != set(pseudos.keys()):
            err_msg = ("Mismatch between the defined pseudos and the list of "
                       "kinds of the structure. Pseudos: {}; kinds: {}".format(
                        ",".join(pseudos.keys()), ",".join(list(kindnames))))
            raise InputValidationError(err_msg)

        ##############################
        # END OF INITIAL INPUT CHECK #
        ##############################

        # Kpoints converted to uppercase
        if self._use_kpoints:
            kpoints_dict = kpoints.get_dict()

        # I put the first-level keys as uppercase (i.e., namelist and card names)
        # and the second-level keys as lowercase
        # (deeper levels are unchanged)
        input_params = _uppercase_dict(parameters.get_dict(),
                                       dict_name='parameters')
        input_params = {k: _lowercase_dict(v, dict_name=k) 
                        for k, v in input_params.iteritems()}

        # I remove unwanted elements (for the moment, instead, I stop; to change when
        # we setup a reasonable logging)
        for blocked in self._blocked_keywords:
            nl = blocked[0].upper()
            flag = blocked[1].lower()
            defaultvalue = None
            if len(blocked) >= 3:
                defaultvalue = blocked[2]
            if nl in input_params:
                if flag in input_params[nl]:
                    raise InputValidationError(
                        "You cannot specify explicitly the '{}' flag in the '{}' "
                        "namelist or card.".format(flag, nl))
                if defaultvalue is not None:
                    if nl not in input_params:
                        input_params[nl] = {}
                    input_params[nl][flag] = defaultvalue

        # Set some variables (look out at the case! NAMELISTS should be uppercase,
        # internal flag names must be lowercase)
        if 'CONTROL' not in input_params:
            input_params['CONTROL'] = {}
        input_params['CONTROL']['pseudo_dir'] = self.PSEUDO_SUBFOLDER
        input_params['CONTROL']['outdir'] = self.OUTPUT_SUBFOLDER
        input_params['CONTROL']['prefix'] = self.PREFIX

        input_params['CONTROL']['verbosity'] = input_params['CONTROL'].get(
            'verbosity', 'high') # Set to high if not specified

        # ============ I prepare the input site data =============
        # ------------ CELL_PARAMETERS -----------
        cell_parameters_card = "CELL_PARAMETERS angstrom\n"
        for vector in structure.cell:
            cell_parameters_card += ("{0:18.10f} {1:18.10f} {2:18.10f}"
                                     "\n".format(*vector))

        # ------------- ATOMIC_SPECIES ------------
        # I create the subfolder that will contain the pseudopotentials
        tempfolder.get_subfolder(self.PSEUDO_SUBFOLDER, create=True)
        # I create the subfolder with the output data (sometimes Quantum
        # Espresso codes crash if an empty folder is not already there
        tempfolder.get_subfolder(self.OUTPUT_SUBFOLDER, create=True)
                
        atomic_species_card_list = ["ATOMIC_SPECIES\n"]

        # Keep track of the filenames to avoid to overwrite files
        pseudo_filenames = []
        # I add the pseudopotential files to the list of files to be copied
        for kind in structure.kinds:
            # This should not give errors, I already checked before that
            # the list of keys of pseudos and kinds coincides
            ps = pseudos[kind.name]
            if kind.is_alloy() or kind.has_vacancies():
                raise InputValidationError("Kind '{}' is an alloy or has "
                    "vacancies. This is not allowed for pw.x input structures."
                    "".format(kind.name))

            filename = get_unique_filename(ps.filename, pseudo_filenames)
            pseudo_filenames.append(filename)
            # I add this pseudo file to the list of files to copy            
            local_copy_list.append((ps.get_file_abs_path(),
                                   os.path.join(self.PSEUDO_SUBFOLDER,filename)))
            
            atomic_species_card_list.append("{} {} {}\n".format(
                kind.name.ljust(6), kind.mass, filename))
        atomic_species_card = "".join(atomic_species_card_list)
        del atomic_species_card_list # Free memory

        # ------------ ATOMIC_POSITIONS -----------
        atomic_positions_card_list = ["ATOMIC_POSITIONS angstrom\n"]

        # Check on validity of FIXED_COORDS
        fixed_coords_strings = []
        fixed_coords = settings_dict.pop('FIXED_COORDS',None)
        if fixed_coords is None:
            # No fixed_coords specified: I store a list of empty strings
            fixed_coords_strings = [""] * len(structure.sites)            
        else:
            if len(fixed_coords) != len(structure.sites):
                raise InputValidationError(
                    "Input structure contains {:d} sites, but "
                    "fixed_coords has length {:d}".format(len(structure.sites),
                                                          len(fixed_coords)))

            for i, this_atom_fix in enumerate(fixed_coords):
                if len(this_atom_fix) != 3:
                    raise InputValidationError("fixed_coords({:d}) has not length three"
                                               "".format(i+1))
                for fixed_c in this_atom_fix:
                    if not isinstance(fixed_c, bool):
                        raise InputValidationError("fixed_coords({:d}) has non-boolean "
                                                   "elements".format(i+1))

                if_pos_values = [self._if_pos(_) for _ in this_atom_fix]
                fixed_coords_strings.append("  {:d} {:d} {:d}".format(*if_pos_values))
    
    
        for site, fixed_coords_string in zip(
              structure.sites,fixed_coords_strings):
            atomic_positions_card_list.append(
            "{0} {1:18.10f} {2:18.10f} {3:18.10f} {4}\n".format(
                site.kind_name.ljust(6), site.position[0], site.position[1],
                site.position[2], fixed_coords_string))
        atomic_positions_card = "".join(atomic_positions_card_list)
        del atomic_positions_card_list # Free memory

        # I set the variables that must be specified, related to the system
        # Set some variables (look out at the case! NAMELISTS should be
        # uppercase, internal flag names must be lowercase)
        if 'SYSTEM' not in input_params:
            input_params['SYSTEM'] = {}
        input_params['SYSTEM']['ibrav'] = 0
        input_params['SYSTEM']['nat'] = len(structure.sites)
        input_params['SYSTEM']['ntyp'] = len(kindnames)

        # ============ I prepare the k-points =============
        if self._use_kpoints:
            try:
                kpoints_type = kpoints_dict.pop('type')
            except KeyError: 
                raise InputValidationError("No 'type' specified in the "
                                           "kpoints input node.")
        
            if kpoints_type != "gamma":
                try:
                    kpoints_list = kpoints_dict.pop("points")
                    num_kpoints = len(kpoints_list)
                except KeyError:
                    raise InputValidationError(
                        "the kpoints input node does not contain a 'points' "
                        "key")
                except TypeError:
                    raise InputValidationError(
                        "In the kpoints input node, 'points' is not a list")
                if num_kpoints == 0:
                    raise InputValidationError("At least one k point must be "
                        "provided for non-gamma calculations")
    
            if kpoints_dict:
                    raise InputValidationError("The following keys in the "
                        "kpoints input node are not valid: {}".format(
                            ",".join(kpoints_dict.keys())))
                
            kpoints_card_list = ["K_POINTS {}\n".format(kpoints_type)]
    
            if kpoints_type == "automatic":
                if len(kpoints_list) != 6:
                    raise InputValidationError("k-points type is automatic, but "
                        "the 'points' value is not a list of 6 integers")
                try: 
                    kpoints_card_list.append("{:d} {:d} {:d} {:d} {:d} {:d}\n"
                        "".format(*kpoints_list))
                except ValueError:
                    raise InputValidationError(
                        "Some elements  of the 'points' list "
                        "in the input kpoints node are not integers")        
            elif kpoints_type == "gamma":
                # nothing to be written in this case
                pass
            else:
                kpoints_card_list.append("{:d}\n".format(num_kpoints))
                try:
                    if all(len(i)==4 for i in kpoints_list):
                        try:
                            for kpoint in kpoints_list:
                                kpoints_card_list.append(
                                    "  {:18.10f} {:18.10f} {:18.10f} {:18.10f}"
                                    "\n".format(
                                        float(kpoint[0]),float(kpoint[1]),
                                        float(kpoint[2]),float(kpoint[3])))
                        except ValueError:
                            raise InputValidationError(
                                "Invalid number provided for one of the kpoints"
                                " in the 'points' list of the input kpoints "
                                "node. I got: {}".format(kpoint))
                    else:
                        raise InputValidationError(
                            "In the kpoints input node, 'points' must all have "
                            "length four (3 coordinates + last value: weight)")
                except (KeyError, TypeError):
                    raise InputValidationError(
                        "In the kpoints input node, 'points' must be a list "
                        "of k points, and"
                        "each k point must be provided as a list of 4 items: its "
                        "coordinates and its weight")
            kpoints_card = "".join(kpoints_card_list)
            del kpoints_card_list

        # =================== NAMELISTS AND CARDS ========================
        try:
            namelists_toprint = settings_dict.pop('NAMELISTS')
            if not isinstance(namelists_toprint, list):
                raise InputValidationError(
                    "The 'NAMELISTS' value, if specified in the settings input "
                    "node, must be a list of strings")
        except KeyError: # list of namelists not specified; do automatic detection
            try:
                control_nl = input_params['CONTROL']
                calculation_type = control_nl['calculation']
            except KeyError:
                raise InputValidationError(
                    "No 'calculation' in CONTROL namelist."
                    "It is required for automatic detection of the valid list "
                    "of namelists. Otherwise, specify the list of namelists "
                    "using the NAMELISTS key inside the 'settings' input node")
            
            try:
                namelists_toprint = self._automatic_namelists[calculation_type]
            except KeyError:
                sugg_string = get_suggestion(calculation_type,
                                             self._automatic_namelists.keys())
                raise InputValidationError("Unknown 'calculation' value in "
                    "CONTROL namelist {}. Otherwise, specify the list of "
                    "namelists using the NAMELISTS inside the 'settings' input "
                    "node".format(sugg_string))
        
        input_filename = tempfolder.get_abs_path(self.INPUT_FILE_NAME)

        with open(input_filename,'w') as infile:
            for namelist_name in namelists_toprint:
                infile.write("&{0}\n".format(namelist_name))
                # namelist content; set to {} if not present, so that we leave an 
                # empty namelist
                namelist = input_params.pop(namelist_name,{})
                for k, v in sorted(namelist.iteritems()):
                    infile.write(get_input_data_text(k,v))
                infile.write("/\n")

            # Write cards now
            infile.write(atomic_species_card)
            infile.write(atomic_positions_card)
            if self._use_kpoints:
                infile.write(kpoints_card)
            infile.write(cell_parameters_card)
            #TODO: write CONSTRAINTS
            #TODO: write OCCUPATIONS

        if input_params:
            raise InputValidationError(
                "The following namelists are specified in input_params, but are "
                "not valid namelists for the current type of calculation: "
                "{}".format(",".join(input_params.keys())))

        # operations for restart
        symlink = settings_dict.pop('PARENT_FOLDER_SYMLINK',self._default_symlink_usage) # a boolean
        if symlink:
            if parent_calc_folder is not None:
                # I put the symlink to the old parent ./out folder
                import glob
                if glob.has_magic(self._restart_copy_from):
                    raise NotImplementedError("Implement the symlink with * patterns")
                remote_symlink_list.append(
                        (parent_calc_folder.get_computer().uuid,
                         os.path.join(parent_calc_folder.get_remote_path(),
                                      self._restart_copy_from),
                         self._restart_copy_to
                         ))
        else:
            # copy remote output dir, if specified
            if parent_calc_folder is not None:
                remote_copy_list.append(
                        (parent_calc_folder.get_computer().uuid,
                         os.path.join(parent_calc_folder.get_remote_path(),
                                      self._restart_copy_from),
                         self._restart_copy_to
                         ))

        calcinfo = CalcInfo()

        calcinfo.uuid = self.uuid
        # Empty command line by default
        calcinfo.cmdline_params = settings_dict.pop('CMDLINE', [])
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.stdin_name = self.INPUT_FILE_NAME
        calcinfo.stdout_name = self.OUTPUT_FILE_NAME
        calcinfo.remote_symlink_list = remote_symlink_list
        
        # Retrieve by default the output file and the xml file
        calcinfo.retrieve_list = []        
        calcinfo.retrieve_list.append(self.OUTPUT_FILE_NAME)
        calcinfo.retrieve_list.append(self.DATAFILE_XML)
        settings_retrieve_list = settings_dict.pop('additional_retrieve_list', [])
        calcinfo.retrieve_list += settings_retrieve_list
        calcinfo.retrieve_list += self._internal_retrieve_list
        
        if settings_dict:
            try:
                Parserclass = self.get_parserclass()
                parser = Parserclass(self)
                parser_opts = parser.get_parser_settings_key()
                settings_dict.pop(parser_opts)
            except (KeyError,AttributeError): # the key parser_opts isn't inside the dictionary
                raise InputValidationError("The following keys have been found in "
                  "the settings input node, but were not understood: {}".format(
                  ",".join(settings_dict.keys())))
        
        return calcinfo


    def _if_pos(self,fixed):
        """
        Simple function that returns 0 if fixed is True, 1 otherwise.
        Useful to convert from the boolean value of fixed_coords to the value required
        by Quantum Espresso as if_pos.
        """
        if fixed:
            return 0
        else:
            return 1

    @classmethod
    def _get_linkname_pseudo_prefix(cls):
        """
        The prefix for the name of the link used for the pseudo for kind 'kind'
        
        Args:
            kind: a string for the atomic kind for which we want to get the link name
        """
        return "pseudo_"

    @classmethod
    def _get_linkname_pseudo(cls, kind):
        """
        The name of the link used for the pseudo for kind 'kind'. 
        It appends the pseudo name to the pseudo_prefix, as returned by the
        _get_linkname_pseudo_prefix() method.
        
        Args:
            kind: a string for the atomic kind for which we want to get the
            link name
        """
        return "{}{}".format(cls._get_linkname_pseudo_prefix(),kind)


    def use_pseudos_from_family(self, family_name):
        """
        Set the pseudo to use for all atomic kinds, picking pseudos from the
        family with name family_name.
        
        Note: The structure must already be set.
        
        Args:
            family_name: the name of the group containing the pseudos
        """
        try:
            structure = self.get_input(self.get_linkname('structure'))
        except AttributeError:
            raise ValueError("Structure is not set yet!")

        pseudo_list = get_pseudos_from_structure(structure, family_name)
        
        for kindname, pseudo in pseudo_list.iteritems():
            self.use_pseudo(pseudo, kindname)

    def _set_parent_remotedata(self,remotedata):
        """
        Used to set a parent remotefolder in the restart of ph.
        """
        from aiida.common.exceptions import ValidationError
        
        if not isinstance(remotedata,RemoteData):
            raise ValueError('remotedata must be a RemoteData')
        
        # complain if another remotedata is already found
        input_remote = self.get_inputs(type=RemoteData)
        if input_remote:
            raise ValidationError("Cannot set several parent calculation to a "
                                  "{} calculation".format(self.__class__.__name__))

        self.use_parent_folder(remotedata)

    def create_restart(self,restart_if_failed=False,
                parent_folder_symlink=None):
        """
        Function to restart a calculation that was not completed before 
        (like max walltime reached...) i.e. not to restart a really FAILED calculation.
        Returns a calculation c2, with all links prepared but not stored in DB.
        To submit it simply:
        c2.store_all()
        c2.submit()
        
        :param bool restart_if_failed: restart if parent is failed.
        """
        from aiida.common.datastructures import calc_states
        
        if self.get_state() != calc_states.FINISHED:
            if restart_if_failed:
                pass
            else:
                raise InputValidationError("Calculation to be restarted must be "
                            "in the {} state".format(calc_states.FINISHED) )
        
        if parent_folder_symlink is None:
            parent_folder_symlink = self._default_symlink_usage
        
        calc_inp = self.get_inputs_dict()
        
        old_inp_dict = calc_inp['parameters'].get_dict()
        # add the restart flag
        old_inp_dict['CONTROL']['restart_mode'] = 'restart'
        inp_dict = ParameterData(dict=old_inp_dict) 
        
        remote_folders = self.get_outputs(type=RemoteData)
        if len(remote_folders)!=1:
            raise InputValidationError("More than one output RemoteData found "
                                       "in calculation {}".format(self.pk))
        remote_folder = remote_folders[0]
        
        c2 = self.copy()
        
        labelstring = c2.label + " Restart of {} {}.".format(
                                        self.__class__.__name__,self.pk)
        c2.label = labelstring.lstrip()
        
        # set the new links
        c2.use_parameters(inp_dict)
        c2.use_structure(calc_inp['structure'])
        if self._use_kpoints:
            c2.use_kpoints(calc_inp['kpoints'])
        c2.use_code(calc_inp['code'])
        try:
            old_settings_dict = calc_inp['settings'].get_dict()
        except KeyError:
            old_settings_dict = {}
        if parent_folder_symlink is not None:
            old_settings_dict['PARENT_FOLDER_SYMLINK'] = parent_folder_symlink
            
        if old_settings_dict: # if not empty dictionary
            settings = ParameterData(dict=old_settings_dict)
            c2.use_settings(settings)
            
        c2._set_parent_remotedata( remote_folder )
        
        for pseudo in self.get_inputs(type=UpfData):
            c2.use_pseudo(pseudo, kind=pseudo.element)
        
        return c2

def get_input_data_text(key,val):
    """
    Given a key and a value, return a string (possibly multiline for arrays)
    with the text to be added to the input file.
    
    Args:
        key: the flag name
        val: the flag value. If it is an array, a line for each element
            is produced, with variable indexing starting from 1.
            Each value is formatted using the conv_to_fortran function.
    """
    from aiida.common.utils import conv_to_fortran
    # I don't try to do iterator=iter(val) and catch TypeError because
    # it would also match strings
    if hasattr(val,'__iter__'):
        # a list/array/tuple of values
        list_of_strings = [
            "  {0}({2}) = {1}\n".format(key, conv_to_fortran(itemval),
                                        idx+1)
            for idx, itemval in enumerate(val)]
        return "".join(list_of_strings)
    else:
        # single value
        return "  {0} = {1}\n".format(key, conv_to_fortran(val))

def _lowercase_dict(d, dict_name):
    from collections import Counter
    
    if isinstance(d,dict):
        new_dict = dict((str(k).lower(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            num_items = Counter(str(k).lower() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError("_lowercase_dict accepts only dictionaries as argument")
    
def _uppercase_dict(d, dict_name):
    from collections import Counter
    
    if isinstance(d,dict):
        new_dict = dict((str(k).upper(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            
            num_items = Counter(str(k).upper() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError("_lowercase_dict accepts only dictionaries as argument")

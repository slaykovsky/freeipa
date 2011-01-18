/*jsl:import ipa.js */

/*  Authors:
 *    Pavel Zuna <pzuna@redhat.com>
 *    Endi Sukma Dewata <edewata@redhat.com>
 *
 * Copyright (C) 2010 Red Hat
 * see file 'COPYING' for use and warranty information
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

/* REQUIRES: ipa.js */

IPA.add_dialog = function (spec) {

    spec = spec || {};

    var that = IPA.dialog(spec);

    that.name = spec.name;
    that.title = spec.title;
    that._entity_name = spec.entity_name;

    that.init = function() {

        that.add_button('Add', function() {
            var record = that.get_record();
            that.add(
                record,
                function() {
                    var entity = IPA.get_entity(that.entity_name);
                    var facet = entity.get_facet('search');
                    var table = facet.table;
                    table.refresh();
                    that.close();
                }
            );
        });


        that.add_button('Add and Add Another', function() {
            var record = that.get_record();
            that.add(
                record,
                function() {
                    var entity = IPA.get_entity(that.entity_name);
                    var facet = entity.get_facet('search');
                    var table = facet.table;
                    table.refresh();
                    that.reset();
                }
            );
        });

        that.add_button('Add and Edit', function() {
            var record = that.get_record();
            that.add(
                record,
                function() {
                    that.close();

                    var pkey_name = IPA.metadata[that.entity_name].primary_key;
                    var pkey = record[pkey_name];

                    var state = {};
                    state[that.entity_name + '-facet'] = 'details';
                    state[that.entity_name + '-pkey'] = pkey;
                    $.bbq.pushState(state);
                }
            );
        });

        that.add_button('Cancel', function() {
            that.close();
        });

        that.dialog_init();
    };

    that.add = function(record, on_success, on_error) {

        var pkey_name = IPA.metadata[that.entity_name].primary_key;

        var command = IPA.command({
            method: that.entity_name+'_add',
            on_success: on_success,
            on_error: on_error
        });

        for (var i=0; i<that.fields.length; i++) {
            var field = that.fields[i];

            var value = record[field.name];
            if (!value) continue;

            if (field.name == pkey_name) {
                command.add_arg(value);
            } else {
                command.set_option(field.name, value);
            }
        }

        command.execute();
    };

    that.add_dialog_init = that.init;

    return that;
};


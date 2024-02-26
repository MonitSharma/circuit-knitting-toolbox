# This code is a Qiskit project.

# (C) Copyright IBM 2024.

# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Quantum circuit representation compatible with cut-finding optimizer."""
from __future__ import annotations

import copy
import numpy as np
import string
from numpy.typing import NDArray
from abc import ABC, abstractmethod
from typing import NamedTuple, Hashable, Iterable, cast, Sequence, Union


class CircuitElement(NamedTuple):
    """Named tuple for specifying a circuit element."""

    name: str
    params: list[float | int]
    qubits: Sequence[int | tuple[str, int]]
    gamma: int | float | None


class CircuitInterface(ABC):

    """Base class for accessing and manipulating external circuit
    representations, and for converting external circuit representations
    to the internal representation used by the circuit cutting optimization code.

    Derived classes must override the default implementations of the abstract
    methods defined in this base class.
    """

    @abstractmethod
    def getNumQubits(self):
        """Derived classes must override this function and return the number
        of qubits in the input circuit."""

    @abstractmethod
    def getMultiQubitGates(self):
        """Derived classes must override this function and return a list that
        specifies the multiqubit gates in the input circuit.

        The returned list is of the form:
            [ ... [<unique_index> <gate_specification> <cut_constraints>] ...]

        The <unique_index> can be any object that uniquely identifies the gate
        in the circuit. The <unique_index> can be used as an argument in other
        member functions implemented by the derived class to replace the gate
        with the decomposition determined by the optimizer.

        The <gate_specification> must be of the form of CircuitElement.

        The <gate_name> must be a hashable identifier that can be used to
        look up cutting rules for the specified gate. Gate names are typically
        the Qiskit names of the gates.

        The <qubit_id> must be a non-negative integer with qubits numbered
        starting with zero.  Derived classes are responsible for constructing the
        mappings from external qubit identifiers to the corresponding qubit IDs.

        The <cut_constraints> can be of the form
            None
            []
            [None]
            [<cut_type_1>, ..., <cut_type_n>]

        A cut constraint of None indicates that no constraints are placed
        on how or whether cuts can be performed. An empty list [] or the
        list [None] indicates that no cuts are to be performed and the gate
        is to be applied without cutting. A list of cut types of the form
        [<cut_type_1> ... <cut_type_n>] indicates precisely which types of
        cuts can be considered. In this case, the cut type None must be
        explicitly included to indicate the possibilty of not cutting, if
        not cutting is to be considered. In the current version of the code,
        the allowed cut types are 'None', 'GateCut' and 'WireCut'.
        """

    @abstractmethod
    def insertGateCut(self, gate_ID, cut_type):
        """Derived classes must override this function and mark the specified
        gate as being cut.  The cut types can only be "LO" in this release.
        """

    @abstractmethod
    def insertWireCut(self, gate_ID, input_ID, src_wire_ID, dest_wire_ID, cut_type):
        """Derived classes must override this function and insert a wire cut
        into the output circuit just prior to the specified gate on the wire
        connected to the specified input of that gate.  Gate inputs are
        numbered starting from 1.  The wire/qubit ID of the wire to be cut
        is also provided as input to allow the wire choice to be verified.
        The ID of the new wire/qubit is also provided, which can then be used
        internally in derived classes to create new wires/qubits as needed.
        The cut type can only be "LO" in this release.
        """

    @abstractmethod
    def defineSubcircuits(self, list_of_list_of_wires):
        """Derived classes must override this function.  The input is a
        list of subcircuits where each subcircuit is specified as a
        list of wire IDs.
        """


class SimpleGateList(CircuitInterface):

    """Derived class that converts a simple list of gates into
    the form needed by the circuit-cutting optimizer code.

    Elements of the input list must be instances of :class:`CircuitElement`.
    The only exception to this is a barrier when one is placed across
    all the qubits in a circuit. That is specified by the string: "barrier".

    Qubit names can be any hashable objects. Gate names can also be any
    hashable objects, but they must be consistent with the names used by the
    optimizer to look up cutting rules for the specified gates.

    The constructor can be supplied with a list of qubit names to force a
    preferred ordering in the assignment of numeric qubit IDs to each name.

    Member Variables:

    qubit_names (NametoIDMap): an instance of :class:`NametoIDMap` that maps
    qubit names to numerical qubit IDs.

    num_qubits (int): the number of qubits in the input circuit. Qubit IDs
    whose values are greater than or equal to num_qubits represent qubits
    that were introduced as the result of wire cutting. These qubits are
    assigned generated names of the form ('cut', <qubit_name>) in the
    qubit_names object, where <qubit_name> is the name of the wire/qubit
    that was cut to create the new wire/qubit.

    circuit (list): the internal representation of the circuit, which is
    a list of the following form:

        [ ... [<gate_specification>, None] ...]

    where the qubit names have been replaced with qubit IDs in the gate
    specifications.

    new_circuit (list): a list of gate specifications that define
    the cut circuit. As with circuit, qubit IDs are used to identify
    wires/qubits.

    cut_type (list): a list that assigns cut-type annotations to gates
    in new_circuit.

    new_gate_ID_map (list): a list that maps the positions of gates
    in circuit to their new positions in new_circuit.

    output_wires (list): a list that maps qubit IDs in circuit to the corresponding
    output wires of new_circuit so that observables defined for circuit
    can be remapped to new_circuit.

    subcircuits (list): a list of list of wire IDs, where each list of
    wire IDs defines a subcircuit.
    """

    circuit: list[list[str | None] | list[CircuitElement | None]]
    new_circuit: Sequence[CircuitElement | str | list[str | int]]
    cut_type: list[str | None]
    qubit_names: NameToIDMap
    num_qubits: int
    new_gate_ID_map: NDArray[np.int_]
    output_wires: NDArray[np.int_]

    def __init__(
        self,
        input_circuit: Sequence[CircuitElement | str],
        init_qubit_names: list[Hashable] = [],
    ):
        self.qubit_names = NameToIDMap(init_qubit_names)

        self.circuit = list()
        self.new_circuit = list()
        self.cut_type = list()
        for gate in input_circuit:
            self.cut_type.append(None)
            if not isinstance(gate, CircuitElement):
                assert gate == "barrier"
                self.circuit.append([copy.deepcopy(gate), None])
                self.new_circuit.append(copy.deepcopy(gate))
            else:
                gate_spec = CircuitElement(
                    name=gate.name,
                    params=gate.params,
                    qubits=[self.qubit_names.getID(x) for x in gate.qubits],
                    gamma=gate.gamma,
                )
                self.circuit.append([copy.deepcopy(gate_spec), None])
                self.new_circuit.append(copy.deepcopy(gate_spec))
        self.new_gate_ID_map = np.arange(len(self.circuit), dtype=int)
        self.num_qubits = self.qubit_names.getArraySizeNeeded()
        self.output_wires = np.arange(self.num_qubits, dtype=int)

        # Initialize the list of subcircuits assuming no cutting
        self.subcircuits: Sequence[list[int] | int] = list(list(range(self.num_qubits)))

    def getNumQubits(self) -> int:
        """Return the number of qubits in the input circuit."""

        return self.num_qubits

    def getNumWires(self) -> int:
        """Return the number of wires/qubits in the cut circuit."""

        return self.qubit_names.getNumItems()

    def getMultiQubitGates(
        self,
    ) -> Sequence[Sequence[int | CircuitElement | None | list]]:
        """Extract the multiqubit gates from the circuit and prepend the
        index of the gate in the circuits to the gate specification.

        The elements of the resulting list therefore have the form
            [<index> <gate_specification> <cut_constaints>]

        The <gate_specification> and <cut_constraints> have the forms
        described above.

        The <index> is the list index of the corresponding element in
        self.circuit.
        """
        subcircuit: Sequence[Sequence[int | CircuitElement | None | list]] = list()
        for k, gate in enumerate(self.circuit):
            if gate[0] != "barrier":
                if len(gate[0].qubits) > 1 and gate[0].name != "barrier":  # type: ignore
                    subcircuit = cast(list, subcircuit)
                    subcircuit.append([k] + gate)

        return subcircuit

    def insertGateCut(self, gate_ID: int, cut_type: str) -> None:
        """Mark the specified gate as being cut. The cut type in this release
        can only be "LO".
        """

        gate_pos = self.new_gate_ID_map[gate_ID]
        self.cut_type[gate_pos] = cut_type

    def insertWireCut(
        self,
        gate_ID: int,
        input_ID: int,
        src_wire_ID: int,
        dest_wire_ID: int,
        cut_type: str,
    ) -> None:
        """Insert a wire cut into the output circuit just prior to the
        specified gate on the wire connected to the specified input of
        that gate.  Gate inputs are numbered starting from 1.  The
        wire/qubit ID of the source wire to be cut is also provided as
        input to allow the wire choice to be verified.  The ID of the
        (new) destination wire/qubit must also be provided. The cut
        type in this release can only be "LO".
        """

        gate_pos = self.new_gate_ID_map[gate_ID]
        new_gate_spec = self.new_circuit[gate_pos]

        # Gate inputs are numbered starting from 1, so we must decrement the index to match qubit numbering.
        assert src_wire_ID == new_gate_spec.qubits[input_ID - 1], (
            f"Input wire ID {src_wire_ID} does not match "
            + f"new_circuit wire ID {new_gate_spec.qubits[input_ID-1]}"
        )

        # If the new wire does not yet exist, then define it
        if self.qubit_names.getName(dest_wire_ID) is None:
            wire_name = self.qubit_names.getName(src_wire_ID)
            self.qubit_names.defineID(dest_wire_ID, ("cut", wire_name))

        # Replace src_wire_ID with dest_wire_ID in the part of new_circuit that
        # follows the wire-cut insertion point
        wire_map = list(range(self.qubit_names.getArraySizeNeeded()))
        wire_map[src_wire_ID] = dest_wire_ID

        self.new_circuit = cast(
            Sequence[Union[CircuitElement, list]], self.new_circuit
        )
        self.replaceWireIDs(self.new_circuit[gate_pos:], wire_map)

        # Insert a move operator
        self.new_circuit = cast(list, self.new_circuit)
        self.new_circuit.insert(gate_pos, ["move", src_wire_ID, dest_wire_ID])
        self.cut_type.insert(gate_pos, cut_type)
        self.new_gate_ID_map[gate_ID:] += 1

        # Update the output wires
        op = cast(CircuitElement, self.circuit[gate_ID][0])
        qubit = op.qubits[input_ID - 1]
        self.output_wires[qubit] = dest_wire_ID

    def defineSubcircuits(self, list_of_list_of_wires: list[list[int]]) -> None:
        """Assign subcircuits where each subcircuit is
        specified as a list of wire IDs.
        """

        self.subcircuits = list_of_list_of_wires

    def getWireNames(self) -> list[Hashable]:
        """Return a list of the internal wire names used in the circuit,
        which consists of the original qubit names together with additional
        names of form ("cut", <name>) introduced to represent cut wires.
        """

        return list(self.qubit_names.getItems())

    def exportCutCircuit(
        self,
        name_mapping: None | str = "default",
    ) -> Sequence[CircuitElement | list[str | int]]:
        """Return a list of gates representing the cut circuit.  If None
        is provided as the name_mapping, then the original qubit names are
        used with additional names of form ("cut", <name>) introduced as
        needed to represent cut wires.  If "default" is used as the mapping
        then the defaultWireNameMapping() method defines the name mapping.
        """

        wire_map = self.makeWireMapping(name_mapping)
        out = copy.deepcopy(self.new_circuit)

        out = cast(Sequence[Union[CircuitElement, list[Union[str, int]]]], out)
        wire_map = cast(list[int], wire_map)
        self.replaceWireIDs(out, wire_map)

        return out

    def exportOutputWires(
        self,
        name_mapping: None | str = "default",
    ) -> dict[Hashable, Hashable | tuple[str, Hashable]]:
        """Return a dictionary that maps output qubits in the input circuit
        to the corresponding output wires/qubits in the cut circuit.  If None
        is provided as the name_mapping, then the original qubit names are
        used with additional names of form ("cut", <name>) introduced as
        needed to represent cut wires.  If "default" is used as the mapping
        then the defaultWireNameMapping() method defines the name mapping.
        """

        wire_map = self.makeWireMapping(name_mapping)
        out = dict()
        for in_wire, out_wire in enumerate(self.output_wires):
            out[self.qubit_names.getName(in_wire)] = wire_map[out_wire]
        return out

    def exportSubcircuitsAsString(
        self,
        name_mapping: None | str = "default",
    ) -> str:
        """Return a string that maps qubits/wires in the output circuit
        to subcircuits per the Circuit Knitting Toolbox convention. This
        method only works with mappings to numeric qubit/wire names.
        """

        wire_map = self.makeWireMapping(name_mapping)
        wire_map = cast(list[int], wire_map)

        out: Sequence[int | str] = list(range(self.getNumWires()))
        out = cast(list, out)
        alphabet = string.ascii_uppercase + string.ascii_lowercase
        for k, subcircuit in enumerate(self.subcircuits):
            subcircuit = cast(list[int], subcircuit)
            for wire in subcircuit:
                out[wire_map[wire]] = alphabet[k]
        return "".join(out)

    def makeWireMapping(
        self, name_mapping: None | str | dict
    ) -> Sequence[int | tuple[str, int]]:
        """Return a wire-mapping list given an input specification of a
        name mapping.  If None is provided as the input name_mapping, then
        the original qubit names are mapped to themselves. If "default"
        is used as the name_mapping, then the defaultWireNameMapping()
        method is used to define the name mapping.
        """

        if name_mapping is None:
            name_mapping = dict()
            for name in self.getWireNames():
                name_mapping[name] = name

        elif name_mapping == "default":
            name_mapping = self.defaultWireNameMapping()  # type: ignore

        wire_mapping: list[int | tuple[str, int]] = list()

        for k in self.qubit_names.getIDs():
            name_mapping = cast(dict, name_mapping)
            wire_mapping.append(name_mapping[self.qubit_names.getName(k)])

        return wire_mapping

    def defaultWireNameMapping(self) -> dict[Hashable, int]:
        """Return a dictionary that maps wire names in :func:`self.getWireNames()` to
        default numeric output qubit names when exporting a cut circuit.  Cut
        wires are assigned numeric IDs that are adjacent to the numeric
        ID of the wire prior to cutting so that Move operators are then
        applied against adjacent qubits. This is ensured by the :func:`self.sortOrder()`
        method.
        """

        name_pairs = [(name, self.sortOrder(name)) for name in self.getWireNames()]

        name_pairs.sort(key=lambda x: x[1])

        name_map: dict[Hashable, int] = dict()
        for k, pair in enumerate(name_pairs):
            name_map[pair[0]] = k

        return name_map

    def sortOrder(self, name: Hashable) -> int | float:
        """Order numeric IDs of wires to enable :func:`defaultWireNameMapping`."""

        if isinstance(name, tuple):
            if name[0] == "cut":
                x = self.sortOrder(name[1])
                x_int = int(x)
                x_frac = x - x_int
                return x_int + 0.5 * x_frac + 0.5

        return self.qubit_names.getID(name)

    def replaceWireIDs(
        self,
        gate_list: Sequence[CircuitElement | list[str | int]],
        wire_map: list[int],
    ) -> None:
        """Iterate through a list of gates and replace wire IDs with the
        values defined by the wire_map.
        """
        for inst in gate_list:
            if isinstance(inst, CircuitElement):
                for k in range(len(inst.qubits)):
                    inst.qubits[k] = wire_map[inst.qubits[k]]  #type: ignore
            elif isinstance(inst, list):
                for k in range(1, len(inst)):
                    inst[k] = wire_map[inst[k]] #type: ignore


class NameToIDMap:

    """Class used to construct maps between hashable items (e.g., qubit names)
    and natural numbers (e.g., qubit IDs).
    """

    def __init__(self, init_names: list[Hashable]):
        """Allow the name dictionary to be initialized with the names
        in init_names in the order the names appear in order to force a
        preferred ordering in the assigment of item IDs to those names.
        """

        self.next_ID: int = 0
        self.item_dict: dict[Hashable, int] = dict()
        self.ID_dict: dict[int, Hashable] = dict()

        for name in init_names:
            self.getID(name)

    def getID(self, item_name: Hashable) -> int:
        """Return the numeric ID associated with the specified hashable item.
        If the hashable item does not yet appear in the item dictionary, a new
        item ID is assigned.
        """
        if item_name not in self.item_dict:
            while self.next_ID in self.ID_dict:
                self.next_ID += 1

            self.item_dict[item_name] = self.next_ID
            self.ID_dict[self.next_ID] = item_name
            self.next_ID += 1

        return self.item_dict[item_name]

    def defineID(self, item_ID: int, item_name: Hashable) -> None:
        """Assign a specific ID number to an item name."""

        assert item_ID not in self.ID_dict, f"item ID {item_ID} already assigned"
        assert (
            item_name not in self.item_dict
        ), f"item name {item_name} already assigned"

        self.item_dict[item_name] = item_ID
        self.ID_dict[item_ID] = item_name

    def getName(self, item_ID: int) -> Hashable | None:
        """Return the name associated with the specified item ID.
        None is returned if item_ID does not (yet) exist.
        """

        if item_ID not in self.ID_dict:
            return None

        return self.ID_dict[item_ID]

    def getNumItems(self) -> int:
        """Return the number of hashable items loaded thus far."""

        return len(self.item_dict)

    def getArraySizeNeeded(self) -> int:
        """Return one plus the maximum item ID assigned thus far,
        or zero if no items have been assigned.  The value returned
        is thus the minimum size needed for a Python/Numpy
        array that maps item IDs to other hashables.
        """

        if self.getNumItems() == 0:  # pragma: no cover
            return 0

        return 1 + max(self.ID_dict.keys())

    def getItems(self) -> Iterable[Hashable]:
        """Return the keys of the dictionary of hashable items loaded thus far."""

        return self.item_dict.keys()

    def getIDs(self) -> Iterable[int]:
        """Return the keys of the dictionary of ID's assigned to hashable items loaded thus far."""

        return self.ID_dict.keys()

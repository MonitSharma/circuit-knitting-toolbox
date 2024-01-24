import pytest
from pytest import fixture
from qiskit.circuit.library import EfficientSU2
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import Qubit, Instruction, CircuitInstruction
from circuit_knitting.cutting.cut_finding.circuit_interface import SimpleGateList
from circuit_knitting.cutting.cut_finding.utils import QCtoCCOCircuit, CCOtoQCCircuit

# test circuit 1.
tc_1 = QuantumCircuit(2)
tc_1.h(1)
tc_1.barrier(1)
tc_1.s(0)
tc_1.barrier()
tc_1.cx(1, 0)

# test circuit 2
tc_2 = EfficientSU2(2, entanglement="linear", reps=2).decompose()
tc_2.assign_parameters([0.4] * len(tc_2.parameters), inplace=True)


# test circuit 3
@fixture
def InternalTestCircuit():
    circuit = [
        ("cx", 0, 1),
        ("cx", 2, 3),
        ("cx", 1, 2),
        ("cx", 0, 1),
        ("cx", 2, 3),
        ("h", 0),
        (("rx", 0.4), 0),
    ]
    interface = SimpleGateList(circuit)
    interface.insertGateCut(2, "LO")
    interface.defineSubcircuits([[0, 1], [2, 3]])
    return interface


@pytest.mark.parametrize(
    "test_circuit, known_output",
    [
        (tc_1, [("h", 1), ("barrier", 1), ("s", 0), "barrier", ("cx", 1, 0)]),
        (
            tc_2,
            [
                (("ry", 0.4), 0),
                (("rz", 0.4), 0),
                (("ry", 0.4), 1),
                (("rz", 0.4), 1),
                ("cx", 0, 1),
                (("ry", 0.4), 0),
                (("rz", 0.4), 0),
                (("ry", 0.4), 1),
                (("rz", 0.4), 1),
                ("cx", 0, 1),
                (("ry", 0.4), 0),
                (("rz", 0.4), 0),
                (("ry", 0.4), 1),
                (("rz", 0.4), 1),
            ],
        ),
    ],
)
def test_QCtoCCOCircuit(test_circuit, known_output):
    test_circuit_internal = QCtoCCOCircuit(test_circuit)
    assert test_circuit_internal == known_output

def test_CCOtoQCCircuit(InternalTestCircuit):
    qc_cut = CCOtoQCCircuit(InternalTestCircuit)
    assert qc_cut.data == [
        CircuitInstruction(
            operation=Instruction(name="cx", num_qubits=2, num_clbits=0, params=[]),
            qubits=(
                Qubit(QuantumRegister(4, "q"), 0),
                Qubit(QuantumRegister(4, "q"), 1),
            ),
            clbits=(),
        ),
        CircuitInstruction(
            operation=Instruction(name="cx", num_qubits=2, num_clbits=0, params=[]),
            qubits=(
                Qubit(QuantumRegister(4, "q"), 2),
                Qubit(QuantumRegister(4, "q"), 3),
            ),
            clbits=(),
        ),
        CircuitInstruction(
            operation=Instruction(name="cx", num_qubits=2, num_clbits=0, params=[]),
            qubits=(
                Qubit(QuantumRegister(4, "q"), 0),
                Qubit(QuantumRegister(4, "q"), 1),
            ),
            clbits=(),
        ),
        CircuitInstruction(
            operation=Instruction(name="cx", num_qubits=2, num_clbits=0, params=[]),
            qubits=(
                Qubit(QuantumRegister(4, "q"), 2),
                Qubit(QuantumRegister(4, "q"), 3),
            ),
            clbits=(),
        ),
        CircuitInstruction(
            operation=Instruction(name="h", num_qubits=1, num_clbits=0, params=[]),
            qubits=(Qubit(QuantumRegister(4, "q"), 0),),
            clbits=(),
        ),
        CircuitInstruction(
            operation=Instruction(name="rx", num_qubits=1, num_clbits=0, params=[0.4]),
            qubits=(Qubit(QuantumRegister(4, "q"), 0),),
            clbits=(),
        ),
    ]
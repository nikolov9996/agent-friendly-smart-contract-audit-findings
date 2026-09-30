---
id: 11102
severity: "High"
---

# Malicious tokens can be deployed at deterministic addresses on other chains to steal funds

## Description

When sending an ERC20 across the SuperchainTokenBridge, we assume that the token has the same address on both chains. In sendERC20(), we encode the sent token address in the relay call:
```solidity
bytes memory message = abi.encodeCall(this.relayERC20, (_token, msg.sender, _to, _amount));
```
In relayERC20(), we call crosschainMint() on this address:
```solidity
ISuperchainERC20(_token).crosschainMint(_to, _amount);
```
This means that any two SuperchainERC20 compatible tokens deployed on chains in the same cluster can be exchanged freely with one another. Currently, the plan is for these tokens to be deployed using a generic CREATE2 factory. Given the existence of the same factory on both chains, the inputs into the deterministic generation of the token's address are the salt and the initialization code (which includes constructor arguments).
This means that any Superchain token implementation that either (a) uses a fixed address instead of constructor arguments to allocate initial tokens or ownership of the contract or (b) uses an initialize() function after the constructor for the same purposes, will be deployed to identical addresses with different outcomes.
Note that this is near impossible to avoid because, each time a new chain is added to the interop set, the attack becomes possible. An astute attacker could predeploy token contracts on potential interop chains so that, upon interop being enabled, they would get unlimited minting rights on the legitimate tokens on other chains.

## Proof of Concept

The following test demonstrates the example where funds are sent in an initialize() function. Note that the same attack is possible if ownership is allocated this way, or if these values are set to hardcoded values (such as Gnosis Safes) that may be claimable on the other network.
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import { Test, console } from "forge-std/Test.sol";
import { SuperchainERC20 } from "@optimism/L2/SuperchainERC20.sol";
interface Create2Factory {
    function deploy(uint256 value, bytes32 salt, bytes memory code) external;
    function computeAddress(bytes32 salt, bytes32 codeHash) external view returns(address);
}
contract SuperchainUSDC is SuperchainERC20 {
    function initialize() external {
        require(totalSupply() == 0, "already initialized");
        _mint(msg.sender, 100_000_000e18);
    }
    function name() public pure override returns (string memory) {
        return "Superchain USDC";
    }
    function symbol() public pure override returns (string memory) {
        return "USDC";
    }
}
contract Create2Test is Test {
    Create2Factory CREATE2 = Create2Factory(0x13b0D85CcB8bf860b6b79AF3029fCA081AE9beF2);
    function testCreate2Address() external {
        address honest = address(uint160(uint256(keccak256("honest user"))));
        address malicious = address(uint160(uint256(keccak256("malicious user"))));
        vm.createSelectFork("https://optimism-mainnet.infura.io/v3/fb419f740b7e401bad5bec77d0d285a5");
        // On the original chain, a token is deployed with CREATE2 factory.
        uint before = vm.snapshot();
        bytes memory initCode = type(SuperchainUSDC).creationCode;
        vm.startPrank(honest);
        CREATE2.deploy(0, bytes32(0), initCode);
        SuperchainUSDC honestToken = SuperchainERC20(CREATE2.computeAddress(bytes32(0), keccak256(initCode)));
        honestToken.initialize();
        assertEq(honestToken.balanceOf(honest), 100_000_000e18);
        // On the new chain, a malicious user deploys a token with the same code and claim the assets.
        vm.revertTo(before);
        vm.startPrank(malicious);
        CREATE2.deploy(0, bytes32(0), initCode);
        SuperchainUSDC maliciousToken = SuperchainERC20(CREATE2.computeAddress(bytes32(0), keccak256(initCode)));
        maliciousToken.initialize();
        assertEq(maliciousToken.balanceOf(malicious), 100_000_000e18);
    }
}
```

## Recommendation

SuperchainToken developers must be made aware of the fact that all important values must be set in the token's constructor to ensure only an identical deployment with identical properties can be deployed to the same address.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from the SuperchainTokenBridge’s assumption that an ERC20 token will have the identical contract address on every chain participating in the inter‑operability set. The bridge encodes the token address in the cross‑chain message and, on the destination chain, calls crosschainMint on that address. Because the token contracts are deployed through a deterministic CREATE2 factory, the address is derived solely from the salt and the contract’s initialization bytecode. If a token’s critical state – such as initial supply, ownership, or minting rights – is not fixed in the constructor but instead set later via an initialize() function or hard‑coded values, two contracts with the same bytecode can be deployed to the same address while exhibiting different behaviour. An attacker can therefore pre‑deploy a malicious token on a chain that is expected to join the inter‑op set, using the same salt and factory. When the bridge later attempts to mint on what it believes is the legitimate token, it actually invokes the attacker‑controlled contract, granting unlimited minting rights to the attacker. This allows the attacker to claim the assets that were sent from the honest chain, effectively stealing funds. The issue manifests when users initiate a cross‑chain transfer expecting their tokens to be minted on the counterpart chain; instead they receive nothing or see their balance on the destination chain remain zero while the attacker’s balance inflates. The problem is hard to detect because the address matches the expected one, and the bridge does not verify the deployed bytecode or its hash. It was discovered during a security audit that included a proof‑of‑concept test deploying a token with an initialize() routine that mints a large supply to the attacker. To remediate, token developers must ensure that all essential parameters – initial supply, owner, and any privileged roles – are immutable and set in the constructor so that any contract deployed to the deterministic address must be byte‑for‑byte identical to the legitimate token. Additional mitigations include verifying the code hash on the destination chain, using unique salts per chain, or requiring explicit token registration before allowing cross‑chain minting. The flaw belongs to the class of deterministic‑address token impersonation bugs, where mismatched contract logic at a shared address enables unauthorized minting and fund loss.

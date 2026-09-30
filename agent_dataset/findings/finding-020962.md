---
id: 20962
severity: "High"
---

# `V3Vault.sol` permit signature does not check receiving token address is USDC

## Description

In `V3Vault.sol` there all 3 instances of `permit2.permitTransferFrom()`, all 3 does not check token transfered in is USDC token. Allowing user to craft permit signature from any ERC20 token and Vault will accept it as USDC.

## Proof of Concept

Here is how Vault accept USDC from user. Vault will accept `Uniswap.Permit2` signature transfer allowance from Permit2 then to vault contract.

```solidity
if (params.permitData.length > 0) {
    (ISignatureTransfer.PermitTransferFrom memory permit, bytes memory signature) =
        abi.decode(params.permitData, (ISignatureTransfer.PermitTransferFrom, bytes));
    permit2.permitTransferFrom(
        permit,
        ISignatureTransfer.SignatureTransferDetails(address(this), state.liquidatorCost),
        msg.sender,
        signature
    );
} else {
    // take value from liquidator
    SafeERC20.safeTransferFrom(IERC20(asset), msg.sender, address(this), state.liquidatorCost);
}
```

Below is permit signature struct that can be decoded from user provided data:
    
```solidity
interface ISignatureTransfer is IEIP712 {
    /// @notice The token and amount details for a transfer signed in the permit transfer signature
    struct TokenPermissions {
        // ERC20 token address
        address token;
        // the maximum amount that can be spent
        uint256 amount;
    }

    /// @notice The signed permit message for a single token transfer
    struct PermitTransferFrom {
        TokenPermissions permitted;
        // a unique value for every token owner's signature to prevent signature replays
        uint256 nonce;
        // deadline on the permit signature
        uint256 deadline;
    }
}
```

`V3Vault.sol` needs to check `TokenPermissions.token` is USDC, same as vault main asset.

`Uniswap.permit2.permitTransferFrom()` only checks if the sign signature is correct. This is meaningless as Vault does not validate input data.

This allows users to use any ERC20 token, gives allowance and permits to `Uniswap.Permit2`. The Vault will accept any transfer token from `Permit2` as USDC. Allowing users to deposit any ERC20 token and steal USDC from vault.

## Recommendation

Fix missing user input validations in 3 all instances of `permit2`:

```solidity
if (params.permitData.length > 0) {
    (ISignatureTransfer.PermitTransferFrom memory permit, bytes memory signature) =
        abi.decode(params.permitData, (ISignatureTransfer.PermitTransferFrom, bytes));
    require(permit.permitted.token == asset, "V3Vault: invalid token");
    //@permitted amount is checked inside uniswap Permit2
    permit2.permitTransferFrom(
        permit,
        ISignatureTransfer.SignatureTransferDetails(address(this), state.liquidatorCost),
        msg.sender,
        signature
    );
} else {
    // take value from liquidator
    SafeERC20.safeTransferFrom(IERC20(asset), msg.sender, address(this), state.liquidatorCost);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked token address in the permit flow of V3Vault. The contract accepts a permit2.permitTransferFrom call that includes a TokenPermissions struct specifying the token to be transferred. The code never verifies that the token address matches the vault's designated asset (USDC). As a result, an attacker can craft a valid Permit2 signature for any ERC20 token, submit it as permitData, and the vault will treat the transferred tokens as if they were USDC. This occurs in all three places where permit2.permitTransferFrom is invoked. The root cause is missing input validation: the contract trusts the token field supplied by the user without comparing it to the expected asset. Exploitation steps: attacker selects an ERC20 token they control, obtains a permit signature authorizing the vault to pull a chosen amount, encodes the permit struct into params.permitData, calls the vault function. The vault decodes the struct, forwards it to Permit2, which validates the signature but does not check token type. The vault then receives the attacker’s token and credits it as USDC, allowing the attacker to withdraw USDC from the vault or manipulate accounting. The impact is that funds can be siphoned: the vault’s accounting assumes USDC deposits, but the actual token may be worthless or have a different value, leading to loss of USDC reserves and breaking the protocol’s financial guarantees. The bug manifests when a user supplies a non‑USDC token via the permit path; from the user’s perspective the UI may show a successful deposit of USDC while the balance displayed for USDC increases incorrectly, or the vault may later reject withdrawals because its internal accounting is corrupted. The issue was discovered during a manual audit that inspected the permit handling logic and noticed the absence of a token address check. It can be hard to notice because Permit2’s own validation passes, giving a false sense of safety, and the contract does not emit explicit events about the token type. The class of bug is an “unchecked external input leading to asset type confusion” or “missing validation of token address in permit‑based transfer”. To fix the issue, the contract should compare permit.permitted.token against the vault’s asset address (USDC) and revert if they differ, ensuring that only the intended stablecoin can be accepted through the permit flow. Adding this check restores the invariant that the vault only holds USDC and prevents attackers from depositing arbitrary tokens and stealing USDC.

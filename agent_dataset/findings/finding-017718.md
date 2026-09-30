---
id: 17718
severity: "High"
---

# Any public vault without a delegate can be

## Description

If a public vault is created without a delegate, delegate will have the value of address(0). This is also the value returned by ecrecover for invalid signatures (for example, if v is set to a position number that is not 27 or 28), which allows a malicious actor to cause the signature validation to pass for arbitrary parameters, allowing them to drain a vault using a worthless NFT as collateral. When a new Public Vault is created, the Router calls the init() function on the vault as follows:
```solidity
VaultImplementation(vaultAddr).init(
    VaultImplementation.InitParams(delegate)
);
```
If a delegate wasn't set, this will pass address(0) to the vault. If this value is passed, the vault simply skips the assignment, keeping the delegate variable set to the default 0 value:
```solidity
if (params.delegate != address(0)) {
    delegate = params.delegate;
}
```
Once the delegate is set to the zero address, any commitment can be validated, even if the signature is incorrect. This is because of a quirk in ecrecover which returns address(0) for invalid signatures. A signature can be made invalid by providing a positive integer that is not 27 or 28 as the v value. The result is that the following function call assigns recovered = address(0):
```solidity
address recovered = ecrecover(
    keccak256(
        encodeStrategyData(
            params.lienRequest.strategy,
            params.lienRequest.merkle.root
        )
    ),
    params.lienRequest.v,
    params.lienRequest.r,
    params.lienRequest.s
);
```
To confirm the validity of the signature, the function performs two checks:
```solidity
require(
    recovered == params.lienRequest.strategy.strategist,
    "strategist must match signature"
);
require(
    recovered == owner() || recovered == delegate,
    "invalid strategist"
);
```
These can be easily passed by setting the strategist in the params to address(0). At this point, all checks will pass and the parameters will be accepted as approved by the vault. With this power, a borrower can create params that allow them to borrow the vault's full funds in exchange for a worthless NFT, allowing them to drain the vault and steal all the user's funds. All user's funds held in a vault with no delegate set can be stolen.

## Proof of Concept

no poc

## Recommendation

Add a require statement that the recovered address cannot be the zero address:
```solidity
require(recovered != address(0));
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability occurs in public vault contracts that rely on a delegate address for authorising signature checks. When a vault is instantiated without providing a delegate, the initialization code passes address(0) and the contract deliberately skips assigning a non‑zero delegate, leaving the internal delegate variable at its default zero value. The contract later validates a borrower’s request by recovering the signer address with ecrecover and comparing it to both the strategist address stored in the request and to either the vault owner or the delegate. Because ecrecover returns address(0) for malformed signatures (for example when the v parameter is not 27 or 28), the recovered address becomes zero. The subsequent require statements check that the recovered address equals the strategist and that it equals either the owner or the delegate. If the strategist field in the request is also set to address(0), both checks succeed even though the signature is invalid. This logical flaw allows any attacker to craft a request that passes validation without possessing a legitimate signature, and to specify a worthless NFT as collateral while borrowing the full balance of the vault. As a result the attacker can drain all user funds from any vault that was created without a delegate. The issue was discovered during a manual audit of the vault initialization and signature verification flow, where the conditional assignment of the delegate was noted and the interaction with ecrecover’s zero‑address return value was examined. The bug is subtle because the contract does not explicitly reject a zero‑address delegate, and the signature verification appears to succeed, making it easy to miss during testing. The impact is a complete loss of funds for users of affected vaults, with the user interface showing no error but the vault balance becoming zero after the malicious transaction. The vulnerability belongs to the class of missing authority check or zero‑address authority bypass bugs, where a privileged role is unintentionally left unset, allowing signature validation to be bypassed. To remediate, the contract should enforce that the recovered signer is not the zero address and should require that a non‑zero delegate be provided at vault creation, or otherwise adjust the validation logic to reject zero‑address signers.

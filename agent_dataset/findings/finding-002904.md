---
id: 2904
severity: "High"
---

# Wrong implementation of `EIP712MetaTransaction`

## Description

1. `EIP712MetaTransaction` is a utils contract that intended to be inherited by concrete (actual) contracts, therefore. it’s initializer function should not use the `initializer` modifier, instead, it should use `onlyInitializing` modifier. See the implementation of [openzeppelin `EIP712Upgradeable` initializer function](https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable/blob/v4.5.1/contracts/utils/cryptography/draft-EIP712Upgradeable.sol#L48-L57).

[EIP712MetaTransaction.sol#L102-L114](https://github.com/code-423n4/2022-03-rolla/blob/efe4a3c1af8d77c5dfb5ba110c3507e67a061bdd/quant-protocol/contracts/utils/EIP712MetaTransaction.sol#L102-L114)

```solidity
/// @notice initialize method for EIP712Upgradeable
/// @dev called once after initial deployment and every upgrade.
/// @param _name the user readable name of the signing domain for EIP712
/// @param _version the current major version of the signing domain for EIP712
function initializeEIP712(string memory _name, string memory _version)
    public
    initializer
{
    name = _name;
    version = _version;

    __EIP712_init(_name, _version);
}
```

Otherwise, when the concrete contract’s initializer function (with a `initializer` modifier) is calling EIP712MetaTransaction’s initializer function, it will be mistok as reentered and so that it will be reverted (unless in the context of a constructor, e.g. Using @openzeppelin/hardhat-upgrades `deployProxy()` to initialize).

```solidity
/**
 * @dev Modifier to protect an initializer function from being invoked twice.
 */
modifier initializer() {
    // If the contract is initializing we ignore whether _initialized is set in order to support multiple
    // inheritance patterns, but we only do this in the context of a constructor, because in other contexts the
    // contract may have been reentered.
    require(_initializing ? _isConstructor() : !_initialized, "Initializable: contract is already initialized");

    bool isTopLevelCall = !_initializing;
    if (isTopLevelCall) {
        _initializing = true;
        _initialized = true;
    }

    _;

    if (isTopLevelCall) {
        _initializing = false;
    }
}
```

See also: <https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable/releases/tag/v4.4.1>

2. `initializer` can only be called once, it can not be “called once after every upgrade”.

[EIP712MetaTransaction.sol#L102-L114](https://github.com/code-423n4/2022-03-rolla/blob/efe4a3c1af8d77c5dfb5ba110c3507e67a061bdd/quant-protocol/contracts/utils/EIP712MetaTransaction.sol#L102-L114)

```solidity
/// @notice initialize method for EIP712Upgradeable
/// @dev called once after initial deployment.
/// @param _name the user readable name of the signing domain for EIP712
/// @param _version the current major version of the signing domain for EIP712
function initializeEIP712(string memory _name, string memory _version)
    public
    initializer
{
    name = _name;
    version = _version;

    __EIP712_init(_name, _version);
}
```

3. A utils contract that is not expected to be deployed as a standalone contract should be declared as `abstract`. It’s `initializer` function should be `internal`.

See the implementation of [openzeppelin `EIP712Upgradeable`](https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable/blob/v4.5.1/contracts/utils/cryptography/draft-EIP712Upgradeable.sol#L28).

```solidity
abstract contract EIP712Upgradeable is Initializable {
    // ...
}
```

## Proof of Concept

no poc

## Recommendation

Change to:

```solidity
abstract contract EIP712MetaTransaction is EIP712Upgradeable {
    // ...
}

/// @notice initialize method for EIP712Upgradeable
/// @dev called once after initial deployment.
/// @param _name the user readable name of the signing domain for EIP712
/// @param _version the current major version of the signing domain for EIP712
function __EIP712MetaTransaction_init(string memory _name, string memory _version)
    internal
    onlyInitializing
{
    name = _name;
    version = _version;

    __EIP712_init(_name, _version);
}
```

> Resolved in [RollaProject/quant-protocol@25112fa](https://github.com/RollaProject/quant-protocol/commit/25112fa93a650f7b889e8472faf75dd5c471cdf2), but upgradeability was later removed as per [RollaProject/quant-protocol#90](https://github.com/RollaProject/quant-protocol/pull/90).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in an improperly implemented EIP712 meta‑transaction utility contract that is meant to be inherited by application contracts. The contract defines an initialization function that uses OpenZeppelin’s `initializer` modifier, which is designed for a top‑level initializer that can only be executed once for the whole contract hierarchy. Because the utility contract is not abstract and its initializer is declared `public` with the `initializer` modifier, a derived contract that also contains an `initializer` will invoke the base initializer during its own initialization sequence. OpenZeppelin’s `initializer` logic interprets this call as a re‑entry attempt and triggers the `require` guard, causing the transaction to revert unless the call occurs inside a constructor. Consequently, the expected domain separator for EIP712 signatures is never set after deployment or after an upgrade, breaking the meta‑transaction verification flow. The root cause is the misuse of the `initializer` modifier instead of the intended `onlyInitializing` (or `internal` visibility) for utility contracts, combined with the failure to mark the contract as `abstract`. This design flaw makes the initialization routine non‑reusable across upgrades: the comment in the source claims the function can be called "once after every upgrade," but the `initializer` modifier enforces a single execution for the entire inheritance chain, so subsequent upgrades cannot re‑initialise the EIP712 domain. From a user perspective, attempts to interact with the protocol via meta‑transactions may suddenly revert with generic errors, leading to symptoms such as "transaction failed," "no receipt returned," or "signature verification failed" even though the user correctly signed the payload. The issue was identified during a manual audit of the contract’s inheritance structure and its compliance with OpenZeppelin’s upgradeable patterns. It is subtle because the code compiles without warnings and the mistake does not affect static analysis of the function body; only at runtime does the re‑entrancy guard abort the call. The impact is primarily functional: the protocol becomes unable to process signed meta‑transactions after deployment or after an upgrade, effectively freezing certain user flows and potentially causing loss of confidence or funds if users are unable to complete expected operations. The recommended fix is to declare the contract as `abstract`, change the initializer to `internal` (or `private`) visibility, replace the `initializer` modifier with `onlyInitializing`, and rename the function to follow the double‑underscore convention (`__EIP712MetaTransaction_init`). This aligns the utility contract with OpenZeppelin’s upgradeable patterns, ensures that the domain separator can be correctly set during the derived contract’s initialization, and restores the ability to re‑initialize after upgrades without triggering the re‑entrancy guard.

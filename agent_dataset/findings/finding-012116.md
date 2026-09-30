---
id: 12116
severity: "Critical"
---

# Confused Deputy in contributeToPool()

## Description

In the GatherCore contract, the isPoolCurrency global variable indicates if the current pool uses an ERC20 or ETH as the currency. When isPoolCurrency, the corresponding ERC20 address is set at poolCurrency. All the following asset movements such as contributePoolCurrency() and sendPoolCurrencyForRefund() rely on the ERC20 contract deployed at poolCurrency. Based on that, there are two ways for contributors to transfer assets into the pool. If the pool uses ERC20, a contributor should invoke contributePoolCurrency(). If the pool uses ETH, contributeToPool() should be called. Here, we identiﬁed a confused deputy issue in both of them. As shown in the code snippet below, both functions collect the assets, implicitly (ETH) or explicitly (ERC20), before calling contribute() to update the internal asset records. However, there's no sanity check to ensure that the current pool is conﬁgured with the asset that the msg.sender is sending in.

```solidity
function contributePoolCurrency(uint256 _amount)
    external
    require(
        poolCurrency.balanceOf(msg.sender) >= _amount,
        "BALANCE < CONTRIBUTION"
    );
    poolCurrency.safeTransferFrom(msg.sender, address(this), _amount);
    contribute(msg.sender, _amount);
```

```solidity
function contributeToPool()
    external
    payable
    contribute(msg.sender, msg.value);
```

For example, a bad actor could send in 0.001 ETH with contributeToPool() to top-up 1015 poolCurrency. If poolCurrency is USDT which has 6 decimals, the bad actor could invoke withdrawContribution() right after the contributeToPool() call and get 1 millions USDT back. On the other hand, if a bad actor is about to exploit this vulnerability through contributePoolCurrency() with a similar trick mentioned above, the poolCurrency.balanceOf() and poolCurrency.safeTransferFrom() calls fail as the compiler is likely to check the code size of the poolCurrency address. Since a pool conﬁgured with ETH as the currency has poolCurrency == address(0), the attack through contributePoolCurrency() could not happen.

## Proof of Concept

no poc

## Recommendation

Check isPoolCurrency in contributePoolCurrency() and contributeToPool().

```solidity
function contributeToPool()
    external
    payable
    require(!isPoolCurrency, "POOL_CONTRIBUTION_MISMATCH");
    contribute(msg.sender, msg.value);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a confused‑deputy flaw in the contribution functions of the GatherCore contract. The contract stores a flag isPoolCurrency that indicates whether a pool is configured to accept an ERC20 token (isPoolCurrency true) or native ETH (isPoolCurrency false). Two public entry points – contributePoolCurrency(uint256) for ERC20 and contributeToPool() payable for ETH – both forward the received amount to an internal function contribute() that updates the pool’s accounting records. However, neither function validates that the asset type being sent matches the pool’s configured currency. Consequently, when a pool is set up for an ERC20 token, an attacker can call the payable contributeToPool() and send a small amount of ETH. The contract records the ETH value as if it were an amount of the ERC20 token, inflating the internal balance. Later, when the attacker invokes withdrawContribution(), the contract transfers the recorded (inflated) ERC20 amount from the pool to the attacker, effectively allowing the theft of tokens that were never deposited. The root cause is the missing sanity check on isPoolCurrency (or its inverse) before accepting contributions. Exploitation requires only a single transaction that sends ETH to a pool expecting an ERC20 token, followed by a withdrawal call. The impact is critical: funds can be drained from any ERC20‑based pool, undermining the protocol’s financial integrity and harming all contributors and token holders. The issue manifests when the pool’s currency flag is true (ERC20) but the payable function is used; the UI may show a successful contribution with no error, while the internal accounting becomes inconsistent, leading to unexpected large token withdrawals or sudden depletion of pool balances. It was discovered during a formal security audit (Peckshield) by reviewing the contribution logic and noticing the absence of asset‑type verification. The bug is subtle because both functions appear legitimate and the mismatch is not obvious from the contract’s external interface, making it easy to overlook during testing. To remediate, each contribution entry point must enforce that the asset being sent matches the pool’s configuration: the ERC20 function should require isPoolCurrency to be true, and the payable function should require isPoolCurrency to be false, rejecting mismatched contributions before they affect accounting. This aligns the contract’s behavior with its intended business logic that a pool can only accept the currency it was configured for, preventing the accounting distortion that leads to token loss.

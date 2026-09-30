---
id: 16873
severity: "High"
---

# Depeg event can happen at incorrect price

## Description

Depeg event can still happen when the price of a pegged asset is equal to the strike price of a Vault which is incorrect.

This docs clearly mentions:

“When the price of a pegged asset is below the strike price of a Vault, a Keeper(could be anyone) will trigger the depeg event and both Vaults(hedge and risk) will swap their total assets with the other party.” - <https://code4rena.com/contests/2022-09-y2k-finance-contest>

## Proof of Concept

1. Assume strike price of vault is 1 and current price of pegged asset is also 1
2. User calls [triggerDepeg](https://github.com/code-423n4/2022-09-y2k-finance/blob/main/src/Controller.sol#L148) function which calls isDisaster modifier to check the depeg eligibility
3. Now lets see [isDisaster](https://github.com/code-423n4/2022-09-y2k-finance/blob/main/src/Controller.sol#L83) modifier

```solidity
modifier isDisaster(uint256 marketIndex, uint256 epochEnd) {
    address[] memory vaultsAddress = vaultFactory.getVaults(marketIndex);
    if(
        vaultsAddress.length != VAULTS_LENGTH
    )
        revert MarketDoesNotExist(marketIndex);

    address vaultAddress = vaultsAddress[0];
    Vault vault = Vault(vaultAddress);

    if(vault.idExists(epochEnd) == false)
        revert EpochNotExist();

    if(
        vault.strikePrice() < getLatestPrice(vault.tokenInsured())
    )
        revert PriceNotAtStrikePrice(getLatestPrice(vault.tokenInsured()));

    if(
        vault.idEpochBegin(epochEnd) > block.timestamp)
        revert EpochNotStarted();

    if(
        block.timestamp > epochEnd
    )
        revert EpochExpired();
    _;
}
```

4. Assume block.timestamp is at correct timestamp (between idEpochBegin and epochEnd), so none of revert execute. Lets look into the interesting one at

```solidity
if(
    vault.strikePrice() < getLatestPrice(vault.tokenInsured())
)
    revert PriceNotAtStrikePrice(getLatestPrice(vault.tokenInsured()));
```

5. Since in our case price of vault=price of pegged asset so if condition does not execute and finally isDisaster completes without any revert meaning go ahead of depeg
6. But this is incorrect since price is still not below strike price and is just equal

## Recommendation

Change the isDisaster modifier to revert when price of a pegged asset is equal to the strike price of a Vault

```solidity
if(
    vault.strikePrice() <= getLatestPrice(vault.tokenInsured())
)
    revert PriceNotAtStrikePrice(getLatestPrice(vault.tokenInsured()));
```

After discussion, the docs clearly state only below the strike Price
     
     
    This docs clearly mentions:
    
    "When the price of a pegged asset is below the strike price of a Vault, a Keeper(could be anyone) will trigger the depeg event and both Vaults(hedge and risk) will swap their total assets with the other party." - https://code4rena.com/contests/2022-09-y2k-finance-contest

@MiguelBits Exactly when it is below the strike price but in this case depeg is happening when price is equal and not below. Can you please suggest?

Oh I see what you mean, need to correct it!

Ah, a matter of when the equality sign matters a lot. Critically, in this case. Agree with warden that it should be `<=` and not `<` only.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the depeg trigger logic of the Y2K Finance vault system. The protocol is designed to allow a keeper to call the depeg event only when the market price of a pegged asset falls strictly below the strike price of a vault. However, the isDisaster modifier that guards the triggerDepeg function uses a strict less‑than comparison (vault.strikePrice() < currentPrice) to decide whether the condition is satisfied. Because the comparison does not include the equality case, a situation where the asset price is exactly equal to the strike price bypasses the revert, and the function proceeds as if a depeg condition were met. This mismatch between the documented business rule (price must be *below* the strike) and the implemented check creates a logical flaw that can be exploited.

An attacker, or any keeper, can observe that the price oracle reports a value equal to the strike price and, while the epoch is active, invoke triggerDepeg. The isDisaster modifier will not revert, allowing the depeg routine to swap the total assets of the hedge and risk vaults. From the user’s perspective, the vault balances are suddenly transferred to the opposite side even though market conditions have not deteriorated. Users may see their expected hedge position disappear, balances reset to zero, or unexpected asset transfers in the UI, leading to confusion and potential financial loss. The protocol’s accounting assumptions—that a depeg only occurs after a genuine price drop—are violated, breaking the intended risk management model.

The issue is discovered during a Code4rena audit, where a proof‑of‑concept demonstrated the flaw by setting the strike price to 1 and the oracle price to 1, then calling triggerDepeg. All other temporal checks (epoch start, not expired, vault existence) pass, and the only price check fails to fire because it uses ‘<’ instead of ‘<=’. This subtle off‑by‑one error can be hard to notice because the transaction does not revert; instead it performs a state‑changing swap that appears legitimate on‑chain, making the bug quiet yet impactful.

To remediate the problem, the price comparison should be tightened to reject the equality case. Replacing the ‘<’ operator with ‘<=’ (or adding an explicit equality check that reverts) aligns the contract logic with the documented requirement that a depeg only triggers when the market price is *below* the strike price. This change prevents accidental swaps when the price is merely equal, preserving the financial integrity of the vaults and ensuring that users only experience a depeg under the intended market conditions.

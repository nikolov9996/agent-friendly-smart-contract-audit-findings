---
id: 21699
severity: "High"
---

# There is a calculation error in `AuraVault::redeem

## Description

The amount of funds that users can withdraw decreases, leading to a loss of funds for users.

## Proof of Concept

```solidity
function redeem(
    uint256 shares,
    address receiver,
    address owner
) public virtual override(IERC4626, ERC4626) returns (uint256) {
    require(shares <= maxRedeem(owner), "ERC4626: redeem more than max");

    // Redeem assets from Aura reward pool and send to "receiver"
    uint256 assets = IPool(rewardPool).redeem(shares, address(this), address(this));

    _withdraw(_msgSender(), receiver, owner, assets, shares);

    return assets;
}
```
We can see that `AuraVault::redeem()` confuses AuraVault’s shares with `rewardPool`’s shares. AuraVault’s shares need to be converted into AuraVault’s underlying tokens (assets) before they can be withdrawn. This is particularly problematic because, as we know from the `rewardPool` contract address, `rewardPool::redeem()` functions the same way as `rewardPool::withdraw()`.
<https://vscode.blockscan.com/ethereum/0x00A7BA8Ae7bca0B10A32Ea1f8e2a1Da980c6CAd2>
```solidity
function redeem(
    uint256 shares,
    address receiver,
    address owner
) external virtual override returns (uint256) {
    return withdraw(shares, receiver, owner);
}
```
Moreover, in the `rewardPool`, the ratio of share to asset is always 1:1.

**Scenario Example:**

Let’s assume that in `AuraVault`, the ratio of share to asset is always 1:2. In this case, if a user withdraws 1 share, they will ultimately receive only 1 asset; whereas, they should have received 2 assets.

## Recommendation

```solidity
function redeem(
    uint256 shares,
    address receiver,
    address owner
) public virtual override(IERC4626, ERC4626) returns (uint256) {
    require(shares <= maxRedeem(owner), "ERC4626: redeem more than max");
    uint256 assets = previewRedeem(shares);

    // Redeem assets from Aura reward pool and send to "receiver"
    assets = IPool(rewardPool).redeem(assets, address(this), address(this));

    _withdraw(_msgSender(), receiver, owner, assets, shares);

    return assets;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the redeem function of the AuraVault contract, where the amount of assets returned to a user is calculated incorrectly. Instead of converting the caller’s vault shares into the underlying asset amount, the function passes the raw share value directly to the external rewardPool’s redeem method. The rewardPool expects its own share units, which are defined at a 1:1 ratio with assets, while AuraVault’s shares represent a larger amount of underlying tokens (for example, a 1:2 share‑to‑asset ratio). As a result, when a user redeems N shares, the vault calls rewardPool.redeem(N) and receives only N assets, whereas the user is entitled to 2 × N assets according to the vault’s accounting. This mis‑alignment causes users to receive fewer tokens than they should, effectively losing funds. The issue manifests whenever the redeem function is invoked, and it is especially problematic when the vault’s share‑to‑asset conversion factor differs from the rewardPool’s. Affected parties include any holder of AuraVault shares, the protocol’s accounting system, and downstream users who rely on correct withdrawal amounts. The flaw was discovered during a Code4rena audit by comparing the intended previewRedeem conversion with the actual implementation, revealing that the contract confuses vault shares with rewardPool shares. Because the transaction does not revert, the bug can be hard to notice; the UI may show a successful redemption while the transferred token amount is lower than expected, leading to symptoms such as “my balance became zero after redeeming” or “I received no refund”. This violates the business logic that each share should correspond to a predictable amount of assets, breaking the accounting invariants of the vault. Exploitation follows a straightforward flow: a user (or attacker) calls redeem with a certain number of shares, the contract forwards that same number to rewardPool.redeem, receives an insufficient asset amount, and then records the share burn while delivering the shortfall to the receiver, causing a net loss. To remediate the issue, the redeem implementation should first compute the correct asset amount using the vault’s previewRedeem (or an equivalent conversion) and then pass that asset value to rewardPool.redeem, ensuring that the share‑to‑asset ratio is respected. In generic terms, this is a miscalculation bug arising from an incorrect conversion between internal share units and external asset units, leading to under‑withdrawal and potential fund loss.

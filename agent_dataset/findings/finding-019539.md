---
id: 19539
severity: "High"
---

# Protocol mints less rsETH on deposit than intended

## Description

Price of rsETH is calculated as `totalLockedETH / rsETHSupply`. rsETH price is used to calculate rsETH amount to mint when user deposits. Formulas are following:

- `rsethAmountToMint = amount * assetPrice / rsEthPrice`
- `rsEthPrice = totalEthLocked / rsETHSupply`

Problem is that it transfers deposit amount before calculation of `rsethAmountToMint`. It increases `totalEthLocked`. As a result rsethAmountToMint is less than intended because rsEthPrice is higher.

For example:

1. Suppose `totalEthLocked` = 10e18, assetPrice = 1e18, rsETHSupply = 10e18
2. User deposits 30e18. He expects to receive 30e18 rsETH
3. However actual received amount will be `30e18 * 1e18 / ((30e18 * 1e18 + 10e18 * 1e18) / 10e18) = 7.5e18`

## Proof of Concept

Here you can see that it firstly transfers asset to `address(this)`, then calculates amount to mint:

```solidity
function depositAsset(
    address asset,
    uint256 depositAmount
)
    external
    whenNotPaused
    nonReentrant
    onlySupportedAsset(asset)
{
    ...

    if (!IERC20(asset).transferFrom(msg.sender, address(this), depositAmount)) {
        revert TokenTransferFailed();
    }

    // interactions
    uint256 rsethAmountMinted = _mintRsETH(asset, depositAmount);

    emit AssetDeposit(asset, depositAmount, rsethAmountMinted);
}
```

There is long chain of calls:

```
_mintRsETH()
    getRsETHAmountToMint()
        LRTOracle().getRSETHPrice()
            getTotalAssetDeposits()
                getTotalAssetDeposits()
```

Finally `getTotalAssetDeposits()` uses current `balanceOf()`, which was increased before by transferring deposit amount:

```solidity
function getAssetDistributionData(address asset)
    public
    view
    override
    onlySupportedAsset(asset)
    returns (uint256 assetLyingInDepositPool, uint256 assetLyingInNDCs, uint256 assetStakedInEigenLayer)
{
    // Question: is here the right place to have this? Could it be in LRTConfig?
    assetLyingInDepositPool = IERC20(asset).balanceOf(address(this));

    uint256 ndcsCount = nodeDelegatorQueue.length;
    for (uint256 i; i < ndcsCount;) {
        assetLyingInNDCs += IERC20(asset).balanceOf(nodeDelegatorQueue[i]);
        assetStakedInEigenLayer += INodeDelegator(nodeDelegatorQueue[i]).getAssetBalance(asset);
        unchecked {
            ++i;
        }
    }
}
```

## Recommendation

Transfer tokens in the end:

```solidity
function depositAsset(
    address asset,
    uint256 depositAmount
)
    external
    whenNotPaused
    nonReentrant
    onlySupportedAsset(asset)
{
    ...

    uint256 rsethAmountMinted = _mintRsETH(asset, depositAmount);

    if (!IERC20(asset).transferFrom(msg.sender, address(this), depositAmount)) {
        revert TokenTransferFailed();
    }

    emit AssetDeposit(asset, depositAmount, rsethAmountMinted);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a mis‑ordering of operations in the deposit function of the rsETH protocol. When a user deposits an asset, the contract first transfers the deposited tokens into its own balance and only afterwards calculates how many rsETH tokens to mint. The rsETH price is derived from the ratio totalLockedETH / rsETHSupply, which uses the contract’s current token balance. Because the balance has already been increased by the just‑received deposit, the computed price is higher than it would have been before the transfer, so the minting formula (deposit amount * asset price / rsETH price) yields a smaller rsETH amount than the user expects. For example, with a pre‑deposit pool of 10 ETH and a supply of 10 rsETH, a deposit of 30 ETH should yield 30 rsETH, but the contract mints only 7.5 rsETH due to the inflated price. This bug can be exploited by any user making a deposit, effectively losing a portion of their value; an attacker could repeatedly deposit and withdraw to extract value from the price distortion. The issue occurs every time the deposit function is called because the state change (balance increase) happens before the price calculation, and it affects all participants who rely on the protocol’s accounting guarantees. It was discovered during a formal audit by Code4rena, where the call chain revealed that the price oracle reads the contract’s balance after the transfer. The problem is subtle because the price formula appears correct in isolation, and the balance change is hidden inside a low‑level view function, making the discrepancy easy to miss in testing. The correct fix is to perform the minting calculation before moving the tokens, or to compute the price based on the pre‑deposit balance rather than the updated balance, ensuring that the amount of rsETH minted matches the user’s expectation. This class of bug is a state‑dependent pricing error caused by an ordering flaw, leading to users receiving fewer tokens than they should, which violates the protocol’s economic assumptions and can erode trust.

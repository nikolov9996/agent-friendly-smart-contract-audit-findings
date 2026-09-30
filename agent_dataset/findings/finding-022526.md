---
id: 22526
severity: "High"
---

# Liquidation fees are permanently frozen on

## Description

There is no treatment of liquidation fees in SGL, they are frozen on Penrose YB account.
There are 3 kinds of fees, borrow/interest and liquidation ones. The latter miss the handling logic, so such funds are accumulated and frozen.
Protocol-wide loss of funds, which otherwise would be channelled to stakers.
Interest fees are accumulated in the accrueInfo.feesEarnedFraction variable:
cts/markets/singularity/SGLCommon.sol#L103-L105
```solidity
uint256 feeAmount = (extraAmount * protocolFee) / FEE_PRECISION; // % of interest paid goes to fee
feeFraction = (feeAmount * _totalAsset.base) / (fullAssetAmount - feeAmount);
_accrueInfo.feesEarnedFraction += feeFraction.toUint128();
```
Which is then accumulated on internal Penrose account via withdrawing feeShares = _removeAsset(_feeTo, msg.sender, balanceOf[address(penrose)]):
cts/Penrose.sol#L565-L568
```solidity
function _depositFeesToTwTap(IMarket market, ITwTap twTap) private {
    if (!isMarketRegistered[address(market)]) revert NotValid();
    uint256 feeShares = market.refreshPenroseFees();
```
cts/markets/singularity/Singularity.sol#L285-L298
```solidity
function refreshPenroseFees() external onlyOwner returns (uint256 feeShares) {
    address _feeTo = address(penrose);
    // withdraw the fees accumulated in `accrueInfo.feesEarnedFraction` to the balance of `feeTo`.
    if (accrueInfo.feesEarnedFraction > 0) {
        _accrue();
        uint256 _feesEarnedFraction = accrueInfo.feesEarnedFraction;
        balanceOf[_feeTo] += _feesEarnedFraction;
        emit Transfer(address(0), _feeTo, _feesEarnedFraction);
        accrueInfo.feesEarnedFraction = 0;
        emit LogWithdrawFees(_feeTo, _feesEarnedFraction);
    }
    feeShares = _removeAsset(_feeTo, msg.sender, balanceOf[_feeTo]);
}
```
cts/markets/singularity/SGLCommon.sol#L199-L216
```solidity
function _removeAsset(address from, address to, uint256 fraction) internal returns (uint256 share) {
    if (totalAsset.base == 0) {
        return 0;
    }
    Rebase memory _totalAsset = totalAsset;
    uint256 allShare = _totalAsset.elastic + yieldBox.toShare(assetId, totalBorrow.elastic, false);
    share = (fraction * allShare) / _totalAsset.base;
    _totalAsset.base -= fraction.toUint128();
    if (_totalAsset.base < 1000) revert MinLimit();
    balanceOf[from] -= fraction;
    emit Transfer(from, address(0), fraction);
    _totalAsset.elastic -= share.toUint128();
    totalAsset = _totalAsset;
    emit LogRemoveAsset(from, to, share, fraction);
    yieldBox.transfer(address(this), to, assetId, share);
}
```
However, liquidation fees are being placed to Penrose account directly and aren't included in the feeShares = share variable above:
cts/markets/singularity/SGLLiquidation.sol#L297-L312
```solidity
function _extractLiquidationFees(uint256 extraShare, uint256 callerReward)
{
    callerShare = (extraShare * callerReward) / FEE_PRECISION; // y% of profit goes to caller.
    feeShare = extraShare - callerShare; // rest goes to the fee
    if (feeShare > 0) {
        uint256 feeAmount = yieldBox.toAmount(assetId, feeShare, false);
        yieldBox.depositAsset(assetId, address(this), address(penrose), feeAmount, 0);
    }
    if (callerShare > 0) {
        uint256 callerAmount = yieldBox.toAmount(assetId, callerShare, false);
        yieldBox.depositAsset(assetId, address(this), msg.sender, callerAmount, 0);
    }
}
```
But _depositFeesToTwTap() uses only refreshPenroseFees() returned yieldBox.toAmount(_assetId, feeShares, false), which consists of interest and borrowing fees only:
cts/Penrose.sol#L565-L578
```solidity
function _depositFeesToTwTap(IMarket market, ITwTap twTap) private {
    uint256 feeShares = market.refreshPenroseFees();
    yieldBox.withdraw(_assetId, address(this), address(this), 0, feeShares);
    uint256 rewardTokenId = twTap.rewardTokenIndex(_asset);
    uint256 feeAmount = yieldBox.toAmount(_assetId, feeShares, false);
    _distributeOnTwTap(feeAmount, rewardTokenId, _asset, twTap);
}
```
This way liquidation fees accumulated on Penrose's YB account are frozen there as there are no Singularity fees distribution mechanics besides withdrawAllMarketFees() ! _depositFeesToTwTap():
cts/Penrose.sol#L240-L255
```solidity
/// @notice Loop through the master contracts and call `_depositFeesToTwTap()` to each one of their clones.
/// @param markets_ Singularity &/ BigBang markets array
/// @param twTap the TwTap contract
function withdrawAllMarketFees(IMarket[] calldata markets_, ITwTap twTap)
    external onlyOwner notPaused
{
    if (address(twTap) == address(0)) revert ZeroAddress();
    uint256 length = markets_.length;
    unchecked {
        for (uint256 i; i < length;) {
            _depositFeesToTwTap(markets_[i], twTap);
            ++i;
        }
    }
    emit ProtocolWithdrawal(markets_, block.timestamp);
}
```

## Proof of Concept

no poc

## Recommendation

Consider placing liquidation fees into Penrose internal account, leaving them with common YB account of SGL, e.g.:
cts/markets/singularity/SGLLiquidation.sol#L304-L307
```solidity
if (feeShare > 0) {
    uint256 feeAmount = yieldBox.toAmount(assetId, feeShare, false);
    uint256 fullAssetAmount = yieldBox.toAmount(assetId, totalAsset.elastic, false) + totalBorrow.elastic;
    uint256 feeFraction = (feeAmount * totalAsset.base) / fullAssetAmount;
    balanceOf[address(penrose)] += feeFraction;
    totalAsset.base += feeFraction.toUint128();
    totalAsset.elastic += feeShare.toUint128();
    yieldBox.depositAsset(assetId, address(this), address(this), 0, feeShare);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a permanent freezing of liquidation fees inside the Penrose YieldBox (YB) account. In the protocol three fee categories exist: borrowing/interest fees and liquidation fees. Borrowing and interest fees are correctly recorded in the accrueInfo.feesEarnedFraction variable and later withdrawn through the refreshPenroseFees() function, which returns a feeShares amount that is subsequently converted to a token amount and distributed to stakers via the _depositFeesToTwTap() routine. Liquidation fees, however, are handled by the _extractLiquidationFees() function, which deposits the raw fee amount directly into the Penrose YB account using yieldBox.depositAsset. This deposit bypasses the accounting path that updates accrueInfo.feesEarnedFraction, and the refreshPenroseFees() call does not include these liquidation fees when calculating feeShares. Consequently, when the protocol owner invokes withdrawAllMarketFees() to pull fees from each market, only interest and borrowing fees are withdrawn; the liquidation fees remain locked in the Penrose YB balance with no further distribution mechanism. The root cause is the missing integration of liquidation fee accounting into the fee‑withdrawal flow, effectively creating a dead‑end bucket for those funds. An attacker can exploit this by triggering many liquidations, causing a large amount of fees to be siphoned into the frozen bucket, thereby reducing the total fee pool that should be shared with stakers. The impact is a protocol‑wide loss of revenue: stakers receive lower or zero rewards, users may notice that expected refunds or fee rebates never arrive, and the overall economics of the system are weakened. The issue manifests only after a liquidation event when feeShare is greater than zero; the Penrose YB balance grows silently, but no UI or accounting report shows a corresponding increase in distributed rewards, making the problem hard to spot. The bug was discovered during a manual audit of fee handling logic, where the auditor observed that liquidation fees were never referenced in the fee‑withdrawal functions. To remediate, the liquidation fee amount should be converted into a fee fraction and added to the same accounting structures used for interest fees (e.g., accrueInfo.feesEarnedFraction or balanceOf[penrose] with proper base/elastic updates), or a dedicated withdrawal path should be introduced so that liquidation fees are included in the feeShares returned by refreshPenroseFees and subsequently distributed to stakers.

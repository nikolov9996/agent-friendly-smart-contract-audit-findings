---
id: 17807
severity: "High"
---

# debtToMint incorrectly treats feeAdjustment

## Description

_debtToMint() will return 0 decimals amounts and sqthToSell in depositAuction() will be insignificant, leading to ignoring the market orders used and depositing auction to be void as no external funding will be brought in.
feeAdjustment=_calcFeeAdjustment() is (squeethEthPrice*feeRate)/10000 and have 18 decimals.
wSqueethToMint=(_amount*debt)/(collateral+(debt*feeAdjustment)) will have 36 decimals in numerator and the same 36 in denominator, yielding 0 decimals figure.
That figure is sqthToSell, so no market buying orders will be ever filled.
depositAuction() will malfunction all the time, either reverting or producing less WETH and less CRAB than desired, i.e. there will be no deposit auction as market order part is needed to bring in the liquidity to be distributed.
Setting the severity to be high as this is system malfunction with material impact and no prerequisites.
feeAdjustment is treated as if it has no decimals:
Netting.sol#L476-L485
```solidity
/**
* @dev calculates wSqueeth minted when amount is deposited
* @param _amount to deposit into crab
*/
function _debtToMint(uint256 _amount) internal view returns (uint256) {
    uint256 feeAdjustment = _calcFeeAdjustment();
    (,, uint256 collateral, uint256 debt) = ICrabStrategyV2(crab).getVaultDetails();
    uint256 wSqueethToMint = (_amount * debt) / (collateral + (debt * feeAdjustment));
    return wSqueethToMint;
}
```
while it has 18 decimals:
Netting.sol#L795-L800
```solidity
function _calcFeeAdjustment() internal view returns (uint256) {
    uint256 feeRate = IController(sqthController).feeRate();
    if (feeRate == 0) return 0;
    uint256 squeethEthPrice = IOracle(oracle).getTwap(ethSqueethPool, sqth, weth, sqthTwapPeriod, true);
    return (squeethEthPrice * feeRate) / 10000;
}
```
As sqthToSell to be insignificant, there will be no Squeeth selling at all:
Netting.sol#L491-L504
```solidity
function depositAuction(DepositAuctionParams calldata _p) external onlyOwner {
    _checkOTCPrice(_p.clearingPrice, false);
    /**
    * step 1: get eth from mm
    * step 2: get eth from deposit usdc
    * step 3: crab deposit
    * step 4: flash deposit
    * step 5: send sqth to mms
    * step 6: send crab to depositors
    */
    uint256 initCrabBalance = IERC20(crab).balanceOf(address(this));
    uint256 initEthBalance = address(this).balance;
    uint256 sqthToSell = _debtToMint(_p.totalDeposit);
```
This renders sqth buying orders block void, i.e. it will be always _p.orders[0].quantity>=remainingToSell:
Netting.sol#L504-L524
```solidity
uint256 sqthToSell = _debtToMint(_p.totalDeposit);
// step 1 get all the eth in
uint256 remainingToSell = sqthToSell;
for (uint256 i = 0; i < _p.orders.length; i++) {
    require(_p.orders[i].isBuying, "auction order not buying sqth");
    require(_p.orders[i].price >= _p.clearingPrice, "buy order price less than clearing");
    _checkOrder(_p.orders[i]);
    if (_p.orders[i].quantity >= remainingToSell) {
        IWETH(weth).transferFrom(
            _p.orders[i].trader, address(this), (remainingToSell * _p.clearingPrice) / 1e18
        );
        remainingToSell = 0;
        break;
    } else {
        IWETH(weth).transferFrom(
            _p.orders[i].trader, address(this), (_p.orders[i].quantity * _p.clearingPrice) / 1e18
        );
        remainingToSell -= _p.orders[i].quantity;
    }
}
require(remainingToSell == 0, "not enough buy orders for sqth");
```

## Proof of Concept

no poc

## Recommendation

Consider adding decimals treatment, for example:
Netting.sol#L476-L485
```solidity
/**
* @dev calculates wSqueeth minted when amount is deposited
* @param _amount to deposit into crab
*/
function _debtToMint(uint256 _amount) internal view returns (uint256) {
    uint256 feeAdjustment = _calcFeeAdjustment();
    (,, uint256 collateral, uint256 debt) = ICrabStrategyV2(crab).getVaultDetails();
    uint256 wSqueethToMint = (_amount * debt) / (collateral + (debt * feeAdjustment) / 1e18);
    return wSqueethToMint;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a decimal‑handling error in the function that computes how much wSqueeth should be minted when a user deposits ETH into the Crab strategy. The contract calculates a feeAdjustment value with 18 decimal places, but later treats this value as if it had no decimals when it is added to the collateral term in the denominator of the wSqueeth‑to‑mint formula. Because the numerator and denominator are both scaled by 10^36 while the feeAdjustment is not scaled down, the integer division truncates the result to a value that is effectively zero. Consequently the variable sqthToSell, which drives the market‑buy orders in the depositAuction routine, becomes negligible. When depositAuction is executed, the loop that matches buying orders sees a remainingToSell of zero, causing either an immediate revert (due to the final require that remainingToSell == 0) or a situation where no market orders are filled and the contract mints far fewer WETH and CRAB tokens than the depositor expects. From a user’s perspective the deposit appears to succeed – the transaction does not fail – but the expected token balances do not increase, or they increase only marginally, leading to the perception that funds have disappeared or that a refund is missing. The impact is a systemic malfunction: every deposit that triggers the auction will either revert or result in an incomplete distribution of assets, affecting all participants who rely on the auction to provide liquidity, including regular users, liquidity providers, and the protocol itself. The bug was uncovered during a formal audit when the auditors examined the arithmetic in _debtToMint and noticed that feeAdjustment, which carries 18 decimals, was used without the appropriate scaling factor. The issue is subtle because the raw numbers are non‑zero and the contract does not emit an explicit error for the zero‑value calculation, making it easy to miss during casual testing. The root cause belongs to the class of precision‑loss or decimal‑mis‑treatment bugs, where mixed‑scale values are combined without proper normalization. To remediate the problem the feeAdjustment term must be divided by 1e18 (or otherwise scaled) before being added to the collateral term, ensuring that the denominator reflects the correct magnitude and that the resulting wSqueeth amount retains its intended precision. This adjustment restores the proper size of sqthToSell, allowing market buying orders to be executed and the depositAuction to function as designed, thereby aligning the actual token distribution with user expectations.

